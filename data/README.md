# Data Directory

This directory stores datasets, document caches, vector database files, and processed text chunks for the project.

## Structure (Planned for Future Phases)

- `raw/`: Raw uploaded PDF/TXT legal document samples.
- `processed/`: Extracted text, cleaned documents, and metadata chunks.
- `vector_store/`: FAISS or Chroma local vector index files.

## Security Notice

- Confidential legal documents must never be committed to git.
- The `.gitignore` is configured to ignore all files in this directory except this `README.md`.
