import express, { Express } from "express";
import dotenv from "dotenv";
import multer from "multer";
import path from "path";
import fs from "fs";
import { spawn } from "child_process";

dotenv.config();

const app: Express = express();
const port = process.env.PORT || 3000;

app.use(express.json());

// Ensure uploads directory exists (relative to process cwd)
const uploadsDir = path.resolve(process.cwd(), "uploads");
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
 * Saves file to disk, invokes the Python processor, and returns the inserted timetable source id.
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
        return res.json(result);
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
