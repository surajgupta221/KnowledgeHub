# Q4A Live Demo (5 minutes)

## The shape of a good demo
Tell a story. Do not click randomly. Each step proves one requirement from the Definition of Done.

---

## Pre-Demo Checklist

```bash
# 1. Start the entire stack
docker compose up -d

# 2. Verify all services are running
docker ps | grep knowledgehub

# 3. Verify backend API is responding
curl http://localhost:8000/api/documents/ -H "X-User-ID: user_a"

# 4. Open frontend in browser
# Navigate to http://localhost:5173
```

---

## Step 0: System Architecture (1 minute)

**You say (English):**
"One command starts everything: API server, Postgres with pgvector, mock LLM server, and frontend.
The architecture is: Browser → Vite frontend → FastAPI backend → Postgres + pgvector for embeddings → Mock LLM for streaming.
Multi-user isolation is enforced at the SQL layer—each user can only see and ask about their own documents."

**You say (Hinglish):**
"Ek hi command se poora system chal jaata hai: API, database, LLM, UI sab kuch.
Architecture: Browser → React frontend → FastAPI → PostgreSQL + pgvector embeddings → Mock LLM.
Har user ke docs alag hote hain—database query mein hi filter hota hai, not after."

**Action:** `docker compose ps` to show all services running.

---

## Step 1: Login & Upload (1.5 minutes)

**Requirement:** 
- Upload triggers chunking and embedding
- Each chunk stores the owner id
- Files are linked to the user

**You say (English):**
"Log in as User A. Upload a policy document. Behind the scenes: the document is split into chunks, each chunk is embedded by calling the mock LLM, and the embeddings are stored in pgvector. Crucially, each chunk is marked as owned by User A."

**You say (Hinglish):**
"User A ke naam se login karo. Koi document upload karo. Parde ke peeche: document chote pieces mein bant jaata hai, har piece ko LLM embed karta hai, pgvector mein save hota hai, aur owner_id User A ka hota hai."

**Steps:**
1. Click "Login as User A" button
2. Click "Upload Document" 
3. Enter filename: `HR_Policy_2024.txt`
4. Paste or enter document content (e.g., sample HR policy text)
5. Click "Upload"
6. Wait for success message (check browser console for embedding job id)

**Expected outcome:**
- ✅ Document appears in "My Documents" list
- ✅ Backend logged embedding job queue
- ✅ No errors in browser console or backend logs

---

## Step 2: Ask a Question & Stream (1.5 minutes)

**Requirement:**
- Tokens arrive over SSE (Server-Sent Events)
- The UI shows tokens as they come, not after completion
- Streaming is the entire point—proves LLM response time is masked

**You say (English):**
"Now ask a question about the document. Watch the tokens arrive word-by-word in real time. This is Server-Sent Events (SSE)—the LLM responds one token at a time, and the UI paints them immediately. If this was a slow LLM, you'd see the latency fade across the stream, not freeze the whole browser."

**You say (Hinglish):**
"Ab ek sawal pucho document ke baare mein. Dekho—jawab word-by-word aa raha hai, ek saath nahi. Iska matlab: LLM slow ho to bhi app freeze nahi hogi, streaming chal rahi hai."

**Steps:**
1. Select the uploaded document in the left sidebar
2. Click in the chat input field
3. Type: `What are the key benefits mentioned in this policy?`
4. Click "Send" or press Enter
5. Watch tokens stream in real-time in the chat window

**Expected outcome:**
- ✅ Chat message appears on screen
- ✅ Response tokens stream word-by-word (not all at once)
- ✅ Response completes successfully
- ✅ No console errors

---

## Step 3: Press Stop Mid-Stream (1 minute)

**Requirement:**
- Stop aborts the fetch AND the upstream LLM call
- The backend notices the disconnect and cancels the LLM request
- This saves tokens on a rate-limited API

**You say (English):**
"Ask another question. Midway through the response, click Stop. The UI stops fetching, AND the backend sees the disconnect. It immediately cancels the LLM call so we don't waste tokens on a response the user doesn't want."

**You say (Hinglish):**
"Ek aur question pucho. Jawaab aa raha hai—abhi jab half-way ho, Stop button dabao. App ne fetch band kar di aur backend ne bhi LLM call cancel kar di. Tokens zaaya nahi hue."

**Steps:**
1. Type another question: `How does performance review work?`
2. Click "Send"
3. Wait 2-3 seconds for response tokens to start streaming
4. Click "Stop" button (visible in chat panel during streaming)
5. Observe: tokens stop arriving and no error message appears

**Expected outcome:**
- ✅ Stop button becomes visible during streaming
- ✅ Tokens stop arriving after clicking Stop
- ✅ No error message displayed
- ✅ Chat input becomes enabled again to ask another question
- ✅ Backend logs show upstream fetch was cancelled

---

## Step 4: Switch Users & Verify Access Control (1 minute)

**Requirement:**
- User B gets 404 (not 403) for User A's documents
- The owner filter is in the SQL query itself, not applied after retrieval
- This proves isolation is enforced at the database layer

**You say (English):**
"Logout and login as User B. Go to the documents list. User B sees no documents. If I try to access User A's document by ID (a 404 hack), the backend returns 404—not 'permission denied' but 'document doesn't exist'. This is security by obscurity: the database query itself filters by owner, so the document never even appears in User B's results."

**You say (Hinglish):**
"Ab User B ke naam se login karo. Documents list mein kya dikhta hai? Kuch nahi. Kyunki database query mein hi owner check hai—SQL WHERE mein. Doosre user ko doc dikhta hi nahi, permission denied bolne ki zaroorat nahi."

**Steps:**
1. Click "Logout" button (top-right header)
2. Click "Login as User B" button
3. Observe the documents list is empty
4. (Optional) Try to access a document ID directly via backend API:
   - Open browser DevTools (F12)
   - Run: `fetch('/api/documents/1', {headers: {'X-User-ID': 'user_b'}}).then(r => r.json()).then(console.log)`
   - Verify you get 404 (or "document not found"), not an error

**Expected outcome:**
- ✅ User B login succeeds
- ✅ Documents list shows no items
- ✅ (Optional) Direct fetch returns 404 or empty response

---

## Step 5: Trigger Rate Limit & Retry (1 minute)

**Requirement:**
- The mock LLM randomly returns 429 (rate limited) and 503 (service unavailable)
- The client retries with exponential backoff
- Retry-After header is honored
- The UI never froze—backoff is transparent

**You say (English):**
"The mock LLM randomly returns 429 (rate limited) and 503 (service unavailable) to simulate real-world resilience. Watch this: I'll ask a question. If we hit a rate limit, the client will retry with backoff and honor the Retry-After header. From the user's perspective: the app paused for a moment, then the response continued. No crash, no error modal, no 'please try again later'—just resilience."

**You say (Hinglish):**
"Mock LLM random 429/503 return karta hai real-world ke liye. Question pucho, agar 429 aaya to app khud retry karta hai backoff ke saath. User ko dikhta hai: thoda der laga, phir jawaab aa gaya. Freeze nahi hua, error nahi aaya—sirf resilience."

**Steps:**
1. Ask a question: `What is the annual leave policy?`
2. Monitor the browser network tab (F12 > Network)
3. If you see a 429 or 503 response, note the retry attempts
4. If you don't see a rate limit (randomness), ask another question
5. (To force a rate limit, restart the backend: `docker restart knowledgehub-backend-1`)

**Expected outcome:**
- ✅ If rate limit occurs, response still arrives (retry happened)
- ✅ No user-visible error modal
- ✅ Chat response completes normally

---

## Step 6: Background Job - Summarize Document (1 minute)

**Requirement:**
- Summarization request returns 202 Accepted + job_id immediately
- The work runs in a bounded worker pool (not blocking)
- Client can poll for status
- User gets result without blocking the chat

**You say (English):**
"Now, click 'Summarize' on a document. The server returns immediately with a job ID (202 Accepted), not a wait. Behind the scenes, a background worker is processing the request in a bounded pool (not unlimited threads). You can poll for the result, or close the browser—the job keeps running. This is async work: the request returns instantly, the response comes later via polling."

**You say (Hinglish):**
"Document ko 'Summarize' karo. Server turant job_id de deta hai, wait nahi karata. Parde ke peeche: background worker pool mein kaam chal raha hai. Polling kar sakte ho, ya browser close kar sakte ho—job chal rahi rahegi. Slow kaam background mein, user ko turant response."

**Steps:**
1. Click "Logout" to go back to User A
2. Click "Login as User A" again
3. Open DevTools (F12)
4. In the documents list, click "Summarize" button next to the uploaded document
5. In the Network tab, look for the /api/jobs response
6. Verify response is 202 (not 200)
7. Copy the job_id from the response
8. In the Console, run:
   ```javascript
   // Poll for job status
   async function pollJob(jobId) {
     for (let i = 0; i < 10; i++) {
       const r = await fetch(`/api/jobs/${jobId}`, {headers: {'X-User-ID': 'user_a'}});
       const data = await r.json();
       console.log(`Attempt ${i+1}:`, data.status);
       if (data.status === 'completed') {
         console.log('Job finished:', data);
         break;
       }
       await new Promise(r => setTimeout(r, 2000));
     }
   }
   pollJob('PASTE_JOB_ID_HERE');
   ```
9. Wait for job to complete (or timeout)

**Expected outcome:**
- ✅ Summarize button click returns 202 (not 200)
- ✅ Response includes job_id
- ✅ Polling shows job progressing (pending → in_progress → completed)
- ✅ (Optional) Final result includes summary text

---

## Step 7: Run Tests (1 minute)

**Requirement:**
- All tests pass (103 backend + frontend)
- Tests prove multi-user isolation
- Tests prove retry logic
- Tests prove streaming works

**You say (English):**
"Finally, let's prove this all works. Run the test suites. All 103 backend tests pass, including the multi-user isolation test (User A cannot access User B's documents). Frontend tests validate streaming and UI. These aren't mocks—they're real integration tests against the running system."

**You say (Hinglish):**
"Aakhir mein, proof dikhate hain. Tests chalao. Backend 103 tests pass hote hain, frontend bhi. Security aur retry dono cover hain. Mock nahi, real integration tests hain."

**Steps:**
1. Open a terminal (keep the browser visible)
2. Navigate to the backend folder:
   ```bash
   cd E:\Freelance Project\KnowledgeHub\backend
   pytest -q
   ```
3. Wait for all tests to pass (should complete in ~5 seconds)
4. Verify output: `103 passed`
5. (Optional) Run frontend tests:
   ```bash
   cd E:\Freelance Project\KnowledgeHub\frontend
   npm test
   ```

**Expected outcome:**
- ✅ `103 passed` (backend)
- ✅ Frontend tests pass (or skip if slow)
- ✅ No failures

---

## Step 8: Summary & Key Points (30 seconds)

**You say:**
"That's the demo. Here's what we proved:

1. **One-command startup** — All services (DB, API, LLM, UI) run in Docker
2. **Streaming QA** — Tokens arrive one-by-one over SSE, UI is responsive
3. **Multi-user isolation** — Database query filters by owner, other users see 404
4. **Graceful stop** — Stop button aborts the fetch AND upstream LLM call
5. **Resilient retries** — Rate limits (429/503) are retried with backoff, transparent to user
6. **Async background work** — Summarization returns 202 + job_id, worker pool processes in background
7. **All tests green** — 103 integration tests prove all of the above

This is production-ready."

---

## Troubleshooting

### Backend not running
```bash
docker logs knowledgehub-backend-1
docker restart knowledgehub-backend-1
```

### Frontend can't reach backend
- Check backend is on http://localhost:8000 (not 8001, not container name)
- Check CORS headers (should allow *:5173)
- Check browser Network tab for actual error

### Documents not appearing
- Verify database is healthy: `docker logs knowledgehub-postgres-1`
- Check backend logs for chunking/embedding errors
- Run: `curl http://localhost:8000/api/documents/ -H "X-User-ID: user_a"` to verify API works

### Streaming not working
- Check Network tab for `/api/chat/stream` response
- Verify response Content-Type is `text/event-stream`
- Check browser console for fetch errors

### Tests fail
```bash
cd backend
pytest -xvs
```
Then look at the specific test failure for clues.

