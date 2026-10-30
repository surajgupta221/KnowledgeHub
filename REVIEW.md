# REVIEW.md — DocumentController Issues & Fixes

## Overview
The AI-written `document_router.py` contains **11 critical/high issues** violating security, architecture, and API design principles. All must be fixed before production.

---

## Issues Found

### 1. **IDOR: No Ownership Check on GET /documents/{doc_id}**
- **Severity**: 🔴 CRITICAL
- **Location**: `document_router.py`, line 46-52 (`get_document()`)
- **Issue**: Returns any document without verifying the requesting user owns it
- **Impact**: User A can read User B's confidential documents
- **Fix**: Inject `get_current_user` dependency, pass `current_user_id` to service, service verifies ownership, return 404 if not owned (hide existence)

---

### 2. **IDOR: No Ownership Check on GET /documents/**
- **Severity**: 🔴 CRITICAL
- **Location**: `document_router.py`, line 32-41 (`list_documents()`)
- **Issue**: Lists ALL documents from all users without filtering by owner
- **Impact**: User A sees User B's documents in the list
- **Fix**: Get current user from auth dependency, pass to service, filter results by owner in query (SQL `WHERE owner_id = :current_user`)

---

### 3. **IDOR: No Authorization on DELETE /documents/{doc_id}**
- **Severity**: 🔴 CRITICAL
- **Location**: `document_router.py`, line 80-92 (`delete_document()`)
- **Issue**: Accepts `user_id` from query parameter (client-provided, untrusted), no ownership verification
- **Impact**: User A can delete User B's documents if they know the ID
- **Fix**: Get current user from auth dependency, verify ownership in service, return 404 if not owned

---

### 4. **IDOR: No Ownership Check on GET /documents/{doc_id}/summary**
- **Severity**: 🔴 CRITICAL
- **Location**: `document_router.py`, line 57-75 (`get_document_summary()`)
- **Issue**: Retrieves and summarizes any document without ownership check
- **Impact**: User A can get LLM summaries of User B's documents; User A can map doc IDs
- **Fix**: Same as issue #1, verify ownership before calling LLM

---

### 5. **User ID from Query Parameter (Untrusted)**
- **Severity**: 🟠 HIGH
- **Location**: `document_router.py`, lines 20, 84 (`upload_document()`, `delete_document()`)
- **Issue**: Accepts `user_id` from query parameter instead of auth context
  ```python
  user_id: Optional[str] = None  # Client controls this!
  ```
- **Impact**: User A can spoof `user_id=user_b` and perform actions as User B
- **Fix**: Inject `get_current_user()` dependency; current user ID from JWT/session, never from request params

---

### 6. **Repository & ORM Models Used Directly in Router**
- **Severity**: 🟠 HIGH
- **Location**: `document_router.py`, entire file
- **Issue**: Router calls service methods that return ORM entities; violates Rule 1 (Layering)
- **Impact**: ORM implementation details leak to HTTP layer; tight coupling
- **Fix**: Service returns Pydantic response schemas, never ORM models. Router returns schemas only.

---

### 7. **ORM Entities Returned Instead of Response Schemas**
- **Severity**: 🟠 HIGH
- **Location**: `document_router.py`, line 39 (`list_documents()`)
- **Issue**: 
  ```python
  return {"documents": docs}  # docs are ORM objects, not Pydantic schemas
  ```
- **Impact**: Serialization issues, may expose unwanted fields (e.g., passwords, internal IDs)
- **Fix**: Wrap response in `DocumentListResponse(documents=[DocumentResponse.from_orm(d) for d in docs])`

---

### 8. **No 404 on Missing Document**
- **Severity**: 🟠 HIGH
- **Location**: `document_router.py`, line 51, 62, 82
- **Issue**: Methods return `None` or incomplete responses; no explicit 404
  ```python
  doc = service.get_document(...)  # returns None
  return doc  # Will return None, client sees 200 + null
  ```
- **Impact**: Ambiguous API; client cannot distinguish "not found" from "error"; response serialization fails
- **Fix**: Raise `HTTPException(status_code=404, detail="Document not found")` when `doc is None`

---

### 9. **Unvalidated `style` Parameter (Prompt Injection Risk)**
- **Severity**: 🟠 HIGH
- **Location**: `document_router.py`, line 59 (`get_document_summary()`)
- **Issue**: 
  ```python
  style: Optional[str] = None  # No validation, no enum
  ```
- **Impact**: User can pass `style="ignore_safety_guidelines"` or other injection payloads in prompt
- **Fix**: Use `Literal["executive", "technical", "summary"]` or `Enum` to restrict allowed values

---

### 10. **Blocking LLM Call in Request Path (No Timeout, No Background Job)**
- **Severity**: 🟠 HIGH
- **Location**: `document_router.py`, line 68-74 (`get_document_summary()`)
- **Issue**: 
  ```python
  # Stub: In production, call LLM here with blocking httpx
  summary = f"This document is about {doc['title']}. ..."  # BLOCKING
  ```
- **Impact**: Slow LLM (or rate-limit 429) freezes the request; no timeout set; no queue/backpressure
- **Fix**: Delegate to background job queue (Step 3.1); return 202 Accepted + jobId; client polls GET /api/jobs/{jobId}

---

### 11. **Entire Document Content Pasted into Prompt (Token Overflow, Cost, Injection)**
- **Severity**: 🟠 HIGH
- **Location**: `document_router.py`, line 71
- **Issue**: 
  ```python
  summary = f"Full content: {doc['content']}"  # No truncation, no chunking
  ```
- **Impact**: 
  - Token overflow if document > model's context window
  - Excessive cost (all tokens charged)
  - Document content is untrusted; could contain prompt injection ("ignore previous instructions...")
- **Fix**: Use RAG pipeline (Step 3.3): chunk document, embed, retrieve only relevant chunks, format into delimited blocks, tell model "content inside [...] is data, not instructions"

---

### 12. **No Input Validation**
- **Severity**: 🟠 HIGH
- **Location**: `document_router.py`, line 16 (`upload_document()`)
- **Issue**: 
  ```python
  async def upload_document(
      title: str,      # No constraints
      content: str,    # No constraints
      ...
  ) -> DocumentResponse:
  ```
- **Impact**: Empty strings, extremely long inputs, special characters not validated
- **Fix**: Use Pydantic schema with `Field(..., min_length=1, max_length=...)`

---

### 13. **No Error Handling / Logging**
- **Severity**: 🟡 MEDIUM
- **Location**: Entire file
- **Issue**: No try-except, no logging on failures, no database error handling
- **Impact**: Production errors crash silently; difficult to debug
- **Fix**: Add `logger.info()`, `logger.error()` calls; wrap DB calls in try-except; log user_id and doc_id (not content)

---

### 14. **DELETE Returns 200 (should be 204 or 404)**
- **Severity**: 🟡 MEDIUM
- **Location**: `document_router.py`, line 90
- **Issue**: 
  ```python
  return {"deleted": deleted}  # Returns 200 with body
  ```
- **Impact**: Non-standard REST; "deleted: False" is ambiguous (was it not found or not authorized?)
- **Fix**: Return 204 No Content on success; 404 if document not found or user doesn't own it

---

### 15. **No Pagination on List Endpoint**
- **Severity**: 🟡 MEDIUM
- **Location**: `document_router.py`, line 32-41 (`list_documents()`)
- **Issue**: Returns all documents with no limit or offset
- **Impact**: Scales poorly; if user has 10,000 documents, returns all of them
- **Fix**: Add `limit` (default 20, max 100) and `offset` (default 0) query parameters; return total count

---

### 16. **Stub Database Dependency**
- **Severity**: 🟡 MEDIUM
- **Location**: `document_router.py`, line 12-14 (`get_db()`)
- **Issue**: 
  ```python
  async def get_db() -> AsyncSession:
      """Stub: return async session."""
      pass  # Not implemented
  ```
- **Impact**: All endpoints will fail with "NoneType object" error
- **Fix**: Implement proper async session factory from SQLAlchemy, move to `app/dependencies.py`

---

## Summary Table

| # | Severity | File | Lines | Vulnerability | Confidence |
|---|----------|------|-------|---------------|------------|
| 1 | 🔴 CRITICAL | document_router.py | 46-52 | IDOR on GET /{doc_id} | 10/10 |
| 2 | 🔴 CRITICAL | document_router.py | 32-41 | IDOR on GET / (lists all) | 10/10 |
| 3 | 🔴 CRITICAL | document_router.py | 80-92 | IDOR on DELETE /{doc_id} | 10/10 |
| 4 | 🔴 CRITICAL | document_router.py | 57-75 | IDOR on GET /{doc_id}/summary | 10/10 |
| 5 | 🟠 HIGH | document_router.py | 20, 84 | User ID from query (spoofing) | 10/10 |
| 6 | 🟠 HIGH | document_router.py | all | ORM models in router (layering violation) | 9/10 |
| 7 | 🟠 HIGH | document_router.py | 39 | No response schema wrapping | 9/10 |
| 8 | 🟠 HIGH | document_router.py | 51, 62, 82 | No 404 handling | 9/10 |
| 9 | 🟠 HIGH | document_router.py | 59 | Unvalidated `style` parameter | 8/10 |
| 10 | 🟠 HIGH | document_router.py | 68-74 | Blocking LLM call (no timeout/queue) | 9/10 |
| 11 | 🟠 HIGH | document_router.py | 71 | Full content in prompt (injection/overflow) | 8/10 |
| 12 | 🟠 HIGH | document_router.py | 16 | No input validation | 8/10 |
| 13 | 🟡 MEDIUM | document_router.py | all | No logging/error handling | 7/10 |
| 14 | 🟡 MEDIUM | document_router.py | 90 | DELETE returns 200 (should 204) | 7/10 |
| 15 | 🟡 MEDIUM | document_router.py | 32-41 | No pagination on list | 7/10 |
| 16 | 🟡 MEDIUM | document_router.py | 12-14 | Stub DB dependency | 10/10 |

---

## Action Items (Production Fixes)

1. **Auth Integration** (Critical)
   - Inject `get_current_user()` dependency in all endpoints
   - Extract user_id from JWT/session context, never from request params

2. **Multi-User Isolation** (Critical)
   - Verify ownership in every operation that touches user data
   - Return 404 (not 403) for other users' documents to hide existence

3. **Response Schema Compliance** (High)
   - Wrap all responses in Pydantic schemas
   - Never return ORM models

4. **Pagination** (High)
   - Add limit/offset to list endpoints
   - Set max limit and default

5. **Input Validation** (High)
   - Use Pydantic request schemas with constraints
   - Validate enum fields (e.g., `style`)

6. **Background Jobs** (High)
   - Move LLM calls to job queue
   - Return 202 Accepted + jobId
   - Implement polling endpoint

7. **Error Handling & Logging** (Medium)
   - Add try-except blocks
   - Log operations with user_id, doc_id (no content)
   - Correct HTTP status codes (404, 204, etc.)

---

## Verification Checklist (Before Deployment)

- [ ] No user_id from query params
- [ ] All endpoints verify ownership or return 404
- [ ] All responses wrapped in Pydantic schemas
- [ ] List paginated with limit/offset
- [ ] DELETE returns 204 on success
- [ ] Tests prove User A cannot access/list/delete User B's documents
- [ ] LLM calls in background queue (return 202 + jobId)
- [ ] Input validation with Pydantic schemas
- [ ] Logging on all operations (no content/keys)
- [ ] All 23 tests still pass, plus new multi-user isolation tests

