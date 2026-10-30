# PROMPTS.md — Refactoring Decisions & Agent Instructions

## STEP 1.2: Extract DocumentPermissionService

### Objective
Safe refactor to extract permission logic from `LegacyDocumentService` into a dedicated `DocumentPermissionService` with **zero behavior change**.

### Prompts & Instructions Used

1. **Phase A (Create Legacy Service)**
   - Created `LegacyDocumentService` with embedded permission checks
   - 6 public methods: `get_document()`, `list_documents()`, `delete_document()`, `can_access_document()`, `can_delete_document()`
   - Permission logic: owner check (`doc["owner_id"] == current_user_id`)

2. **Phase B (Characterization Tests First)**
   - Wrote 13 comprehensive tests documenting **current behavior** before refactoring
   - Tests capture: ownership checks, non-owner rejection (return None/False), nonexistent documents, list filtering
   - **All 13 tests PASS** before extraction — establishes green baseline

3. **Phase C (Show Plan Before Editing)**
   - Listed exact files to touch: 
     - Create `document_permission_service.py`
     - Modify `legacy_document_service.py`
     - Create `test_document_permission_service.py`
   - Extraction strategy documented
   - Behavior preservation method: "all 13 characterization tests remain green"

4. **Phase D (Extract Logic)**
   - Created `DocumentPermissionService` with:
     - `can_access_document(doc_id, user_id)` — permission check
     - `can_delete_document(doc_id, user_id)` — delete permission check
     - `get_document_if_owned(doc_id, user_id)` — retrieval with permission guard
     - `_is_owner(doc, user_id)` — internal ownership check
   - Injected into `LegacyDocumentService.__init__(permission_service=None)`
   - Constructor injection pattern (Rule 2 from CLAUDE.md)

5. **Phase E (Preserve Behavior)**
   - All 13 characterization tests still pass (behavior unchanged)
   - 9 new unit tests added for `DocumentPermissionService`
   - **22 tests pass** after extraction (13 legacy + 9 new)
   - Full test suite: **23 tests pass** (includes health check)

### How File Scope Was Limited
- Only touched **4 files**:
  - `backend/app/services/document_permission_service.py` (new)
  - `backend/app/services/legacy_document_service.py` (modified)
  - `backend/tests/test_document_permission_service.py` (new)
  - `backend/tests/test_document_permissions_legacy.py` (new)
- Did not modify routers, repositories, config, or other services
- Did not change any imports or public APIs

### Behavior Preservation Method
1. **Characterization tests first** (13 green tests establish baseline)
2. **Extract without changing signatures** (same method names, parameters, return types)
3. **Rerun all tests** (13 + 9 = 22 pass, proving no behavior change)
4. **Verify full suite** (23 total tests pass)

### git diff --stat Output
```
 backend/app/services/document_permission_service.py    | 57 +++++++++++++
 backend/app/services/legacy_document_service.py        | 58 ++++++++++++++
 backend/tests/test_document_permission_service.py      | 64 +++++++++++++++
 backend/tests/test_document_permissions_legacy.py      | 93 ++++++++++++++++++++++
 4 files changed, 272 insertions(+)
```

### Key Decisions

1. **Dependency Injection via Constructor** (Rule 2)
   - `LegacyDocumentService.__init__(permission_service=None)` accepts optional service
   - If None, creates instance with the same documents store (backward compatible)
   - Allows tests to inject mock permission service

2. **Shared Documents Store** (Rule 1: Layering)
   - `DocumentPermissionService` receives `documents` dict reference
   - Keeps permission logic in one place; document retrieval in another
   - No circular dependencies

3. **Public Signatures Unchanged** (Behavior Preservation)
   - All 6 public methods retain original names and return types
   - Callers of `LegacyDocumentService` see no change
   - Internal implementation delegates to `DocumentPermissionService`

4. **No Agent Overrides**
   - This refactoring followed the plan exactly
   - No rejected agent changes to record
   - All tests passed on first run

### Test Evidence

**Characterization Tests (LegacyDocumentService):**
```
13 tests: owner access, non-owner rejection, nonexistent handling, list filtering, delete checks
Status: PASS (before and after extraction)
```

**Unit Tests (DocumentPermissionService):**
```
9 tests: can_access_document, can_delete_document, get_document_if_owned (success, non-owner, nonexistent)
Status: PASS (new service working correctly)
```

**Full Suite:**
```
23 tests total (1 health + 13 legacy + 9 new)
Status: PASS
```

---

## STEP 2.1: Review & Rewrite DocumentController

### Objective
Review the AI-written `document_router.py`, identify all security/design issues in REVIEW.md, then rewrite to production quality.

### Issues Found & Fixed

16 issues identified (see REVIEW.md for full details):

**Critical (IDOR vulnerabilities):**
1. No ownership check on GET /documents/{doc_id}
2. No ownership check on GET /documents/ (lists all users' docs)
3. No authorization on DELETE /documents/{doc_id}
4. No ownership check on GET /documents/{doc_id}/summary

**High (Security & Architecture):**
5. User ID from query parameter (untrusted, allows spoofing)
6. Repository & ORM models used directly in router (layering violation)
7. ORM entities returned instead of response schemas
8. No 404 on missing document (returns None/200)
9. Unvalidated `style` parameter (prompt injection risk)
10. Blocking LLM call in request path (no timeout, no queue)
11. Full document content pasted into prompt (token overflow, cost, injection)
12. No input validation (empty strings, etc.)

**Medium (Robustness):**
13. No error handling / logging
14. DELETE returns 200 (should be 204 or 404)
15. No pagination on list endpoint
16. Stub database dependency (not implemented)

### How Issues Were Found
- Created deliberately-broken `document_router.py` with all known anti-patterns
- Wrote comprehensive REVIEW.md identifying each issue with severity, location, impact, and fix
- Documented in a table for quick reference

### Production Rewrite

**Files Touched:**
- Modified: `document_router.py` (completely rewritten)
- Created: `document_service.py` (async service with permission checks)
- Created: `document_repository.py` (data access layer)
- Created: `document.py` (ORM model)
- Created: `dependencies.py` (get_db, get_current_user DI)
- Modified: `document_schemas.py` (added constraints)
- Created: `test_document_router.py` (multi-user isolation tests)
- Created: `REVIEW.md` (issue documentation)

**Key Fixes:**

1. **Auth Integration** ✅
   - Inject `get_current_user` dependency (from JWT/session)
   - Current user ID never from query params
   - All operations scoped to current user

2. **Multi-User Isolation** ✅
   - Service verifies ownership in `get_document()`, `delete_document()`, etc.
   - Returns 404 if not owned (hides existence)
   - SQL query includes `WHERE owner_id = :current_user` (not filtering after retrieval)

3. **Response Schemas** ✅
   - All endpoints return Pydantic schemas (DocumentResponse, DocumentListResponse)
   - Never return ORM models
   - Schemas define exactly what fields clients see

4. **Pagination** ✅
   - List endpoint: `limit` (1-100, default 20) + `offset` (default 0)
   - Returns `total` count for pagination UI
   - Query uses `.limit(limit).offset(offset)`

5. **Input Validation** ✅
   - DocumentUploadRequest schema: `title` and `content` have min/max constraints
   - `style` parameter restricted to `Literal["executive", "technical", "summary"]`
   - FastAPI validates before endpoint logic

6. **Correct Status Codes** ✅
   - GET /documents/{doc_id}: 200 on success, 404 if not found/not owned
   - DELETE: 204 No Content on success, 404 if not owned
   - 404 used instead of 403 to hide document existence

7. **Error Handling & Logging** ✅
   - All endpoints wrapped in try-except
   - Logging on all operations: `logger.info()`, `logger.warning()`, `logger.error()`
   - Logs include `user_id`, `doc_id` (never content, keys, or tokens)
   - Exception messages logged but not returned to client

8. **Dependency Injection** ✅
   - `DocumentService` receives `AsyncSession` via `__init__`
   - Router receives `get_db()`, `get_current_user()` as dependencies
   - `DocumentRepository` injected into service

9. **Background LLM (Placeholder)** ✅
   - GET /documents/{doc_id}/summary returns stub message
   - Comments explain: should return 202 Accepted + jobId (Step 3.1)
   - TODO marker for background job queue implementation

10. **Layering (Rule 1)** ✅
    - Router: HTTP, validation, dependency injection
    - Service: Business logic, permission checks
    - Repository: Data access (SQL queries)
    - Schema: API contracts only (Pydantic)
    - ORM Models: Never leave service layer

### Tests Added

**File:** `test_document_router.py` (integration tests)

Test cases proving multi-user isolation:
- User B cannot GET User A's document (returns 404)
- User B's list only shows User B's documents
- User B cannot DELETE User A's document (returns 404)
- User B cannot GET summary of User A's document (returns 404)
- Owner can GET, LIST, DELETE their own documents

All tests use dependency overrides to inject test DB and control `current_user_id`.

### Behavior Verification

**Before & After Comparison:**
- ❌ Before: GET /documents/ returns all documents from all users
- ✅ After: GET /documents/ filters by owner_id in SQL

- ❌ Before: No 404 on missing document, returns None
- ✅ After: Returns 404 with proper error detail

- ❌ Before: user_id from query param (User A can spoof user_b)
- ✅ After: current_user_id from auth dependency (JWT/session)

- ❌ Before: Returns ORM model directly
- ✅ After: Wrapped in Pydantic response schema

- ❌ Before: No pagination (scales poorly)
- ✅ After: Paginated with limit/offset

---

## Section for Rejected Agent Changes

*No agent overrides. Refactoring followed plan exactly.*

---

## Next Steps (Pending Approval)

- ✅ STEP 1.2 complete: Safe refactor documented and tested
- ✅ STEP 2.1 complete: DocumentController reviewed and rewritten to production quality
- ⏳ STEP 2.2: Streaming chat endpoint
- ⏳ STEP 2.3: Fix DocumentList freezing
- ⏳ STEP 3.1: Background job queue
- ⏳ STEP 3.2: Resilient LLM client
- ⏳ STEP 3.3: RAG pipeline
- ⏳ STEP 4: Final verification and defense prep
