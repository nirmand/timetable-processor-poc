# TimeTable Processor
An app to process timetables with complex and diverse formats and structures, and transforming that information into a single, uniform, and usable format class time tables for teachers.

# POC Status
1. Implemented end-to-end workflow (Upload timetable -> Process, Parse and Extract from timetable -> Store in a structured format in database -> Display timetable in Calendar view)
2. Used tech-stack most suitable to specific use case and to keep things simple and efficient (React + Node.JS + Python + Sqlite)

# Future considerations
1. Increasing accuracy of extraction logic, parsing data and output. This requires improvement at this stage.
2. Next.JS (A React framework) + Tailwind and replacing React and Node.JS for Server-side rendering, rich UI, and static site generation.
3. A new step in workflow to pass OCR output to LLM models (such as, OpenAI models or Gemini models) to leverage more context and trained data as OCR libraries are having certain limitations with some characters or hand-written contents.
4. CI/ CD pipeline
5. Using Azure Blob Storage/ AWS S3 for persisting input timetable files

# References
[Architecture](https://github.com/nirmand/timetable-processor-poc/blob/main/architecture.md)
