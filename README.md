# TimeTable Processor
An app to process timetables with complex and diverse formats and structures, and transforming that information into a single, uniform, and usable format class time tables for teachers.

# POC Status
1. Implemented end-to-end workflow (Upload timetable -> Process, Parse and Extract from timetable -> Store in a structured format in database -> Display timetable in Calendar view).
2. Used tech-stack most suitable to specific use case and to keep things simple and efficient (React + Node.JS + Python + Sqlite).
3. Used PaddleOCR for parsing and extracting as it provides higher accuracy on complex, varied, or real-world images compared to other libraries.

# Known Issues/ Limitations
1. Parsing and extraction process requires significant improvements as it's giving a very few correct data. The results are not acceptable in quality and accurancy. The issue is with the parsing and table detaction logic written in Python processor engine which needs to be corrected to make the app reliable. But for now, we have a strong foundation and architecture in place with an end-to-end workflow.

# Future considerations
1. Increasing accuracy of extraction logic, parsing data and output. This requires improvement at this stage.
2. Next.JS (A React framework) + Tailwind and replacing React and Node.JS for Server-side rendering, rich UI, and static site generation.
3. A new step in workflow to pass OCR output to LLM models (such as, OpenAI models or Gemini models) to leverage more context and trained data as OCR libraries are having certain limitations with some characters or hand-written contents.
4. Using Azure Blob Storage/ AWS S3 for persisting input timetable files
5. OpenAPI Specifications for API documentation
6. CI/ CD pipeline

# References
- [Architecture](https://github.com/nirmand/timetable-processor-poc/blob/main/architecture.md)
- [Setup](https://github.com/nirmand/timetable-processor-poc/blob/main/setup.md)
