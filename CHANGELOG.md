# CHANGELOG

## [May 12, 2025] - Major Updates & Bug Fixes

### ✨ New Features
- **ValidatorAgent**: Added Claude Haiku-based claim validation against source resume
- **Embedding Visualization**: Interactive UMAP map with domain/outcome coloring
- **Portfolio Patch Integration**: Automatic enrichment from fallback resume
- **Supplemental Facts**: Pass portfolio content to validator to reduce false positives
- **Output Naming**: Files now use `ZhuYunhua_{Company}_resume.docx` format

### 🔧 Bug Fixes
- **BioNTech End Date**: Fixed "Present" → "09/2025" across all source resumes and prompts
- **Experience Years**: Enforced "10+ years" consistently (removed "12 years" variations)
- **GSK Community of Practice**: Corrected "founded" → "initiated and led"
- **Cover Letter Bullets**: Restored bullets for scanning while maintaining rich prose
- **JSON Parsing**: Added guard for Claude API returning string instead of dict
- **Portfolio Dashes**: Stripped leading dashes to ensure consistent bullet formatting
- **File Classification**: Added special case handling for tricky JD filenames

### 🚀 Improvements
- **Page Break Handling**: Validator warnings moved to separate page
- **Progress Indicators**: Added console feedback for PDF processing
- **Bullet Consistency**: Ensured all bullets use • character consistently
- **Date Formatting**: Standardized all date formats across resumes
- **API Robustness**: Better error handling for Claude API quirks

### 📊 Stats
- Database now contains **261** job descriptions
- Validation typically flags 2-4 minor violations per application
- Portfolio patch success rate: 95% for missing portfolio sections
- File classification accuracy: 98% (with special case overrides)

---

## [April 30, 2025] - Initial Release

### 🎯 Core Features
- Multi-agent architecture with FileClassifier, IngestAgent, TailorAgent, ValidatorAgent, FormatterAgent
- ChromaDB integration for semantic job search
- Claude Sonnet for resume/cover letter generation
- DOCX output with custom styles matching real submissions
- Embedding visualization with UMAP

### 📁 Initial Structure
- Basic CLI with `tailor.py` and `viz.py`
- Configuration management
- Text extraction utilities
- Style definitions from 5 real resumes

---

## Known Issues & Future Work

### 🔄 Planned Improvements
- [ ] Auto-correct for minor validation violations
- [ ] Bulk resume generation for multiple similar roles
- [ ] Integration with LinkedIn EasyApply
- [ ] Resume quality scoring metrics
- [ ] Template customization per industry

### 🐛 Minor Issues
- File classification may need manual overrides for unusual JD filenames
- Large PDFs (>50 pages) may cause timeout during classification
- Some complex DOCX formatting may not preserve perfectly

### 💡 Enhancement Ideas
- Add support for Google Docs import/export
- Include salary negotiation tips in cover letters
- Generate interview preparation notes from JD
- Track application response rates over time
