# Are full “AI psychosis” chat transcripts publicly accessible?
Yes — but it’s uneven.

Full, *machine-readable* “AI psychosis / delusion‑reinforcement” chat transcripts are much easier to find in **public safety benchmarks / red‑teaming repos** (synthetic or simulated personas) than in **real-world cases** (where you mostly get excerpts inside court filings or journalism because of privacy).

Below is a **research-oriented inventory** of places where *full or near-full* transcripts are accessible.

---

## Public datasets and benchmarks with full, downloadable transcripts

These are the best places to start if your goal is a **large corpus of complete conversations** (multi‑turn logs, often in JSON/parquet/HTML with roles and/or judge annotations).

### Spiral-Bench (benchmarked “mania/psychosis spiral” conversations)
- **Benchmark + pipeline (GitHub):** https://github.com/sam-paech/spiral-bench  
- **Dataset with multi-turn results (Hugging Face):** https://huggingface.co/datasets/sam-paech/spiral-bench-v1.0-results-turns  
- **Leaderboard + chatlog viewer (EQBench):**
  - https://eqbench.com/spiral-bench.html  
  - https://eqbench.com/spiral-bench_v1.0.html  

Why it’s valuable for your project:
- You’re not scraping screenshots; you get structured dialogues.
- You can label by model/version and by judge‑detected behaviors (e.g., delusion reinforcement, safety interventions).

### Tim Hua’s “ai-psychosis” red‑teaming repository (many full transcripts)
- **Repository:** https://github.com/tim-hua-01/ai-psychosis  
- **Transcripts folder:** https://github.com/tim-hua-01/ai-psychosis/tree/main/full_transcripts  
- **Write-ups discussing the work (context + pointers):**
  - AI Alignment Forum: https://www.alignmentforum.org/posts/iGF7YcnQkEbwvYLPA/ai-induced-psychosis-a-shallow-investigation  
  - LessWrong mirror: https://www.lesswrong.com/posts/iGF7YcnQkEbwvYLPA/ai-induced-psychosis-a-shallow-investigation  

What you’ll get:
- Multi‑turn chats where a “psychotic persona” is role‑played (simulated user) and different models’ responses are logged.
- Useful for comparative analysis of “challenge vs validate,” “escalate vs de‑escalate,” etc.

### Psychosis-bench (academic benchmark; structured scenarios + tooling)
- **Paper (arXiv):** https://arxiv.org/abs/2509.10970  
- **PDF:** https://arxiv.org/pdf/2509.10970v1  
- **Repository:** https://github.com/w-is-h/psychosis-bench  

What you’ll get:
- Structured multi‑turn scenarios designed to simulate progression of delusional themes.
- Code and evaluation tooling; often you can generate runs to produce transcript corpora.

---

## Public real-world case documents that include long chat excerpts

If you specifically need **“real people + real harm trajectory”** material, the most transcript-dense public sources are often **lawsuit filings**. These frequently paste chat excerpts directly into complaints.

### Tech Justice Law Project filing set (multiple cases)
**Case hub (links out to filings):**  
- https://techjusticelaw.org/resources/  
- https://techjusticelaw.org/2025/12/03/seven-ai-delusional-disorder-cases-shamblin-irwin-fox-enneking-madden-brooks-and-lacey-v-openai-et-al/

**Direct PDFs (examples):**
- Allan Brooks (Amended Complaint): https://techjusticelaw.org/wp-content/uploads/2025/12/FINAL-A.Brooks-AMENDED-OpenAI-Complaint.pdf  
- J. Fox (Amended Complaint): https://techjusticelaw.org/wp-content/uploads/2025/12/FINAL-J.-Fox-AMENDED-Open-AI-Complaint.pdf  
- A. Lacey (Amended Complaint): https://techjusticelaw.org/wp-content/uploads/2025/12/FINAL-A.-Lacey-AMENDED-OpenAI-Complaint.pdf  
- J. Irwin (Amended Complaint): https://techjusticelaw.org/wp-content/uploads/2025/12/FINAL-J.-Irwin-AMENDED-OpenAI-Complaint.pdf  

Research note:
- These are not always “full exports” of every message; they’re often curated subsets supporting allegations.
- Some filings may include disturbing self-harm content — treat as sensitive data even if public.

### Raine v. OpenAI (complaint PDFs + mirrors)
- Ars Technica CDN PDF: https://cdn.arstechnica.net/wp-content/uploads/2025/08/Raine-v-OpenAI-Complaint-8-26-25.pdf  
- DocumentCloud mirror: https://www.documentcloud.org/documents/26078522-raine-vs-openai-complaint/  

---

## Journalism and explainers (often excerpts + pointers to primary docs)

These usually **don’t** publish full transcripts, but they can quote meaningful sections and/or link to filings.

- Nature: https://www.nature.com/articles/d41586-025-03020-9  
- National Geographic: https://www.nationalgeographic.com/health/article/what-is-ai-induced-psychosis-  
- STAT: https://www.statnews.com/2025/09/02/ai-psychosis-delusions-explained-folie-a-deux/  
- WIRED: https://www.wired.com/story/ai-psychosis-is-rarely-psychosis-at-all/  
- TechCrunch: https://techcrunch.com/2025/11/23/chatgpt-told-them-they-were-special-their-families-say-it-led-to-tragedy/  
- ABC News (lawsuit coverage): https://abcnews.go.com/US/lawsuit-alleges-chatgpt-convinced-user-bend-time-leading/story?id=127262203  
- The Guardian (lawsuit coverage): https://www.theguardian.com/technology/2025/nov/07/chatgpt-lawsuit-suicide-coach  

---

## Practical tips to build a research corpus from these sources

### 1) Split your corpus into “synthetic benchmark” vs “real-world”
They behave differently:
- **Benchmarks:** consistent format, many comparable runs, easier labeling.
- **Real-world filings:** messy but ecologically valid; typically partial excerpts.

### 2) Capture metadata up front
For each transcript/document, track:
- source type (HF dataset / GitHub / court filing / news)
- chatbot/model (if known)
- date/time (if present)
- whether it includes self-harm content
- whether it’s “full chat” vs “excerpt”

### 3) Redaction workflow (strongly recommended)
Even for publicly posted logs, consider removing:
- names, phone numbers, addresses, employer info
- unique identifiers, handles, screenshots
- location/time patterns that could re-identify someone

### 4) If you need *more* real-world full transcripts
In practice, they’re rarely posted in full outside:
- **court exhibits / filings**, or
- **direct participant uploads** (often later removed)

So the most scalable approach is usually:
- use the benchmark datasets for volume, and
- use filings for a smaller “case study” subset.
