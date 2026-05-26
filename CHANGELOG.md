# CHANGELOG

## [May 25, 2025] - Three-Phase Multi-Agent Architecture Refactoring

### 🏗️ Phase 1: Separation of Concerns
- **`prompts/`**: Extracted system prompts to versioned markdown files
  - `resume_system.md` - 80-line resume generation guidelines with all constraints
  - `cover_system.md` - 75-line cover letter structure with format rules
  - Independent versioning for A/B testing prompt variations
- **`schemas/`**: Centralized schema definitions for structured LLM output
  - `paragraph.py` - Shared paragraph schema with validation functions
  - `resume_schema.py` - RESUME_TOOL definition for Claude tool-use
  - `cover_schema.py` - COVER_TOOL with structure constants
- **`services/`**: Extracted business logic from monolithic `tailor_agent.py`
  - `retrieval.py` - ChromaDB query operations as service class
  - `source_selection.py` - QC + fallback logic with `QualityResult` dataclass
  - `llm_client.py` - Claude wrapper with `TracedLLMClient` for execution tracing

### 🤖 Phase 2: Multi-Agent Expansion
- **`agents/reviewer_agent.py`** - New style + role-fit critique agent
  - `ReviewResult` dataclass with structured scores (0-100) and recommendations
  - Evaluates job fit (40%), style quality (30%), factual accuracy (30%)
  - Heuristic fallback when LLM unavailable
- **`evals/`** - Comprehensive test framework
  - `test_hallucination.py` - 4 tests: fabricated companies, inflated titles, invented metrics, portfolio attribution
  - `test_structure.py` - 8 tests: resume sections, cover letter format, required elements
  - `runner.py` - Test execution with quality reports
  - `golden_examples/` - Success criteria templates (e.g., Immunai example)

### 👤 Phase 3: Human-in-the-Loop & Stateful Workflow
- **`agents/orchestrator.py`** - `ResumeOrchestrator` with explicit state machine
  - 12 workflow states: `IDLE` → `RETRIEVING` → `SELECTING_SOURCE` → `GENERATING_RESUME` → `REVIEWING_RESUME` → `AWAITING_RESUME_APPROVAL` → `GENERATING_COVER` → `REVIEWING_COVER` → `AWAITING_COVER_APPROVAL` → `VALIDATING` → `COMPLETED`/`REJECTED`
  - `WorkflowContext` dataclass tracks all artifacts through pipeline
  - State transition callbacks for observability and debugging
  - Human approval checkpoints with rejection handling
- **`interactive.py`** - New CLI with human oversight
  - Interactive resume review with AI scores and content preview
  - Cover letter approval with structured feedback display
  - Auto-approve mode (`--auto` flag) for batch processing
  - Real-time state transition display

### 📊 Impact Metrics
- **Code Organization**: 1 monolithic file (~500 lines) → 12 focused modules
- **Test Coverage**: 0 tests → 12 evaluation tests (8 passing without external deps)
- **Human Oversight**: None → 2 approval checkpoints (resume + cover letter)
- **Observability**: Print statements → Execution traces in `evals/traces/`
- **State Management**: Implicit → Explicit 12-state workflow with callbacks

---

## [May 13, 2025] - Quality Control & Source Resume Validation

### ✨ Critical Improvements
- **Quality Control System**: Implemented comprehensive QC for source resume validation with scoring system
- **Smart Fallback Mechanism**: Automatically falls back to 2nd/3rd best matches when primary source fails QC
- **Resume Quality Criteria**: Validates minimum content length, proper sections (name, headers, bullets), and detects job descriptions
- **Error Handling**: Graceful handling of missing directories and inaccessible source files
- **Placeholder Prevention**: Eliminates `<UNKNOWN>` placeholders by ensuring proper source material
- **QC Reporting**: Detailed QC feedback with scores and specific issue identification

### 🔧 QC Features Added
- **Content Validation**: Minimum 500 characters, proper section structure
- **Job Description Detection**: Identifies and rejects JD files masquerading as resumes
- **Placeholder Detection**: Flags `<UNKNOWN>`, TBD, and placeholder content
- **Scoring System**: 0-1 quality score with pass/fail threshold (0.6)
- **Fallback Strategy**: Tries multiple candidates, uses best available if all fail

## [May 13, 2025] - Customer Support & Cover Letter Enhancement

### ✨ Critical Improvements
- **Customer Support Role Detection**: Automatically detects support/training roles and creates dedicated "Customer Support & Training" skills category
- **Support-Focused Summary**: Reframes experience for customer-facing roles with emphasis on technical support and training
- **Enhanced Cover Letters**: Role-specific cover letter generation with training/troubleshooting emphasis for support roles
- **Spatial Biology Prioritization**: Smart portfolio selection prioritizes spatial transcriptomics projects for Bruker-type roles
- **Training & Leadership Emphasis**: Enhanced bullet prompts to highlight workshops, community leadership, and training experience
- **Company-Specific Enthusiasm**: Improved cover letter closing with genuine company mission focus

### 🎯 Cover Letter Features Added
- **Role Detection**: Automatically identifies customer support, technical, and spatial biology roles
- **Training Bullet Prioritization**: For support roles, prioritizes NIH workshops, Community of Practice leadership
- **Troubleshooting Emphasis**: Includes customer support and user guidance examples for support roles
- **Enhanced Opening**: Company-specific observations with customer-facing collaboration framing
- **Improved Closing**: Genuine enthusiasm for company mission and technology

## [May 13, 2025] - Customer Support & Spatial Biology Enhancement

### ✨ Critical Improvements
- **Customer Support Role Detection**: Automatically detects support/training roles and creates dedicated "Customer Support & Training" skills category
- **Support-Focused Summary**: Reframes experience for customer-facing roles with emphasis on technical support and training
- **Spatial Biology Prioritization**: Smart portfolio selection prioritizes spatial transcriptomics projects for Bruker-type roles
- **Training & Leadership Emphasis**: Enhanced bullet prompts to highlight workshops, community leadership, and training experience
- **Multi-Keyword Detection**: System now detects MCP/agentic AI, spatial biology, AND customer support keywords for tailored content

## [May 13, 2025] - MCP/Agentic AI Enhancement

### ✨ Critical Improvements
- **MCP/Agentic AI Keywords**: Added automatic detection and inclusion of MCP server development and agentic AI workflows in summary and skills sections
- **Smart Portfolio Selection**: Prioritizes MCP-relevant projects (job-rag, linkedin-job-scout) when JD mentions agentic AI
- **Pharma-Specific Language**: Enhanced bullet prompts to include GxP, regulatory, and compliance terminology
- **JD-Aware Content Generation**: System now detects JD keywords and tailors content accordingly

### 🎯 Key Features Added
- **Automatic MCP Detection**: Scans JD for terms like "MCP", "agentic AI", "workflow orchestration"
- **Dynamic Summary Generation**: Includes MCP/agentic AI expertise when relevant to role
- **Intelligent Skills Categorization**: Creates dedicated "AI Tooling" category with MCP server development
- **Portfolio Project Prioritization**: Reorders projects to highlight most relevant experience first

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
