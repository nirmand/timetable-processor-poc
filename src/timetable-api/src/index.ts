import express, { Express } from "express";
import dotenv from "dotenv";
import multer from "multer";
import path from "path";
import fs from "fs";
import { spawn } from "child_process";
import Database from "better-sqlite3";

dotenv.config();

const app: Express = express();
const port = process.env.PORT || 3000;

app.use(express.json());

// Enable CORS
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  if (req.method === 'OPTIONS') {
    return res.sendStatus(200);
  }
  next();
});

// Database path (relative to project root)
const DB_PATH = path.resolve(process.cwd(), "..", "..", "db", "timetable.sqlite");

// Ensure uploads directory exists (configurable, defaults to repo root /uploads)
const uploadsDir = process.env.UPLOAD_DIR 
  ? path.resolve(process.env.UPLOAD_DIR) 
  : path.resolve(process.cwd(), "..", "..", "uploads");
if (!fs.existsSync(uploadsDir)) {
  fs.mkdirSync(uploadsDir, { recursive: true });
}

// Multer storage (keep filename safe)
const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, uploadsDir),
  filename: (_req, file, cb) => {
    const safeName = `${Date.now()}-${file.originalname.replace(/[^a-zA-Z0-9.\-_%]/g, "_")}`;
    cb(null, safeName);
  }
});

const upload = multer({
  storage,
  limits: { fileSize: Number(process.env.MAX_UPLOAD_BYTES) || 10 * 1024 * 1024 }, // default 10MB
});

app.get("/health", (_req, res) => {
  res.json({ status: "ok" });
});

/**
 * POST /timetable/upload
 * Expects multipart/form-data with a `file` field.
 * Saves file to disk, invokes the Python processor, and returns the inserted timetable source id with activities.
 */
app.post("/timetable/upload", upload.single("file"), (req, res) => {
  if (!req.file) return res.status(400).json({ error: "No file uploaded" });

  const savedPath = path.resolve(req.file.path);

  // Determine python executable and processor script path
  const python = process.env.PYTHON_PATH || "python";
  // script is expected at ../processor/scripts/run.py relative to this package directory
  const processorScript = path.resolve(process.cwd(), "..", "processor", "scripts", "run.py");

  try {
    const child = spawn(python, [processorScript, savedPath], { stdio: ["ignore", "pipe", "pipe"] });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => (stdout += chunk.toString()));
    child.stderr.on("data", (chunk) => (stderr += chunk.toString()));

    child.on("error", (err) => {
      console.error("Failed to start processor:", err);
      return res.status(500).json({ error: "Failed to start processor", details: String(err) });
    });

    child.on("close", (code) => {
      if (code !== 0) {
        console.error("Processor error (code):", code, "stderr:", stderr);
        return res.status(500).json({ error: "Processor failed", code, details: stderr });
      }

      // Extract last JSON object from stdout (processor prints logs + final JSON)
      const trimmed = stdout.trim();
      const jsonMatch = trimmed.match(/\{[\s\S]*\}$/);
      if (!jsonMatch) {
        return res.status(500).json({ error: "No JSON output from processor", raw: stdout });
      }

      try {
        const result = JSON.parse(jsonMatch[0]);
        const sourceId = result.timetable_source_id;

        if (!sourceId) {
          return res.status(500).json({ error: "No timetable_source_id in processor output" });
        }

        // Read from database
        try {
          const db = new Database(DB_PATH, { readonly: true });
          
          // Get timetable source
          const source = db.prepare(`
            SELECT id, file_path, processed_at 
            FROM timetable_sources 
            WHERE id = ?
          `).get(sourceId) as { id: number; file_path: string; processed_at: string } | undefined;

          if (!source) {
            db.close();
            return res.status(404).json({ error: "Timetable source not found in database" });
          }

          // Get extracted activities
          const activities = db.prepare(`
            SELECT id, day, start_time, end_time, notes 
            FROM extracted_activities 
            WHERE source_id = ?
            ORDER BY id
          `).all(sourceId) as Array<{
            id: number;
            day: string;
            start_time: string;
            end_time: string;
            notes: string | null;
          }>;

          db.close();

          return res.json({
            timetable_source_id: source.id,
            file_path: source.file_path,
            processed_at: source.processed_at,
            activities: activities
          });
        } catch (dbError) {
          console.error("Database error:", dbError);
          return res.status(500).json({ error: "Failed to read from database", details: String(dbError) });
        }
      } catch (e) {
        return res.status(500).json({ error: "Invalid JSON from processor", parseError: String(e), raw: jsonMatch[0] });
      }
    });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "Failed to run processor", details: String(err) });
  }
});

app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});
