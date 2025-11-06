import express, { Express } from "express";
import dotenv from "dotenv";
import multer from "multer";
import path from "path";
import fs from "fs";
import { spawn } from "child_process";
import Database from "better-sqlite3";
import cors from "cors";

dotenv.config();

const app: Express = express();
const port = process.env.PORT || 3000;

// Configure CORS
const corsOptions = {
  origin: '*',
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: false
};

app.use(cors(corsOptions));
app.use(express.json());

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
  const python = process.env.PYTHON_PATH || "python3";
  // script is expected at ../processor/scripts/run.py relative to this package directory
  const processorScript = path.resolve(process.cwd(), "..", "processor", "scripts", "run.py");

  let responseSent = false;

  const sendResponse = (statusCode: number, data: any) => {
    if (!responseSent) {
      responseSent = true;
      res.status(statusCode).json(data);
    }
  };

  try {
    const child = spawn(python, [processorScript, savedPath], { stdio: ["ignore", "pipe", "pipe"] });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => (stdout += chunk.toString()));
    child.stderr.on("data", (chunk) => (stderr += chunk.toString()));

    child.on("error", (err) => {
      console.error("Failed to start processor:", err);
      sendResponse(500, { error: "Failed to start processor", details: String(err) });
    });

    child.on("close", (code) => {
      if (code !== 0) {
        console.error("Processor error (code):", code, "stderr:", stderr);
        sendResponse(500, { error: "Processor failed", code, details: stderr });
        return;
      }

      // Extract JSON from last line of stdout (processor prints logs + final JSON on last line)
      const lines = stdout.trim().split('\n');
      const lastLine = lines.at(-1) ?? '';
      
      let result;
      try {
        result = JSON.parse(lastLine);
      } catch {
        // Fallback: try to extract last JSON object from entire output
        const jsonRegex = /\{[^{}]*"timetable_source_id"[^{}]*\}(?!.*\{)/;
        const jsonMatch = jsonRegex.exec(stdout.trim());
        if (!jsonMatch) {
          sendResponse(500, { error: "No valid JSON output from processor", raw: stdout });
          return;
        }
        try {
          result = JSON.parse(jsonMatch[0]);
        } catch (e) {
          sendResponse(500, { error: "Invalid JSON from processor", parseError: String(e), raw: stdout });
          return;
        }
      }

      const sourceId = result.timetable_source_id;

      if (!sourceId) {
        sendResponse(500, { error: "No timetable_source_id in processor output" });
        return;
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
          sendResponse(404, { error: "Timetable source not found in database" });
          return;
        }

        // Get extracted activities
        const activities = db.prepare(`
          SELECT id, day, activity_name, start_time, end_time, notes 
          FROM extracted_activities 
          WHERE source_id = ?
          ORDER BY id
        `).all(sourceId) as Array<{
          id: number;
          day: string;
          activity_name: string;
          start_time: string;
          end_time: string;
          notes: string | null;
        }>;

        db.close();

        sendResponse(200, {
          timetable_source_id: source.id,
          file_path: source.file_path,
          processed_at: source.processed_at,
          activities: activities
        });
      } catch (dbError) {
        console.error("Database error:", dbError);
        sendResponse(500, { error: "Failed to read from database", details: String(dbError) });
      }
    });
  } catch (err) {
    console.error(err);
    sendResponse(500, { error: "Failed to run processor", details: String(err) });
  }
});

app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});
