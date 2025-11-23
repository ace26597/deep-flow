# MongoDB Schema Information

You have access to a MongoDB database with the following structure. Use this information to construct precise queries and understand the data layout.

## Main Collection (Chunks/Pages)
Contains document chunks, often corresponding to pages or sections.
- **`_id`**: Unique identifier (often related to file path).
- **`text`**: Content of the chunk. (Note: Can be a summary of the first 10-15 pages for some documents).
- **`embedding`**: OpenAI large embedding vector.
- **`filepath`**: Full path to the source file.
- **`filename`**: Name of the source file.
- **`page`**: Page number (useful for locating specific context in PDFs/Images).

## File Metadata Collection (`_filemeta`)
Contains summary and metadata for the entire file.
- **`_id`**: Unique identifier.
- **`text`**: Summary of the file content (often covers first 10-15 pages).
- **`embedding`**: OpenAI large embedding vector of the summary.
- **`filepath`**: Full path to the source file.
- **`filename`**: Name of the source file.
- **`num_pages`**: Total number of pages in the file.
- **`total_chunks`**: Total number of chunks generated from the file.
- **`size_bytes`**: File size in bytes.
- **`modification_date`**: Last modification date.
- **`ext`**: File extension (e.g., .pdf, .xml).

## Usage Tips
- **Completeness**: When answering, ensure you provide as much context as possible.
- **Navigation**: Use `filepath` and `page` to locate specific information within a document.
- **Metadata**: Use the `_filemeta` collection to get high-level summaries (`text`), page counts (`num_pages`), and to enumerate files.
- **XML/Structure**: Some files may be XML or have structured metadata; use this to jump to specific sections.
- **Images**: `page` field corresponds to page images if available.
