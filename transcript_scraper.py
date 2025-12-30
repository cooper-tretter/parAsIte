"""
AI Psychosis Transcript Scraper

Collects full conversation transcripts from research sources:
- Spiral-Bench (HuggingFace): Benchmark conversations with model responses
- Tim Hua ai-psychosis repo (GitHub): Full red-team transcripts
- Psychosis-bench (GitHub): Structured scenarios

NOTE: These are primarily synthetic/red-teamed data, not real-world cases.
Real-world full transcripts are rare (privacy).
"""

import json
import os
import re
import requests
import time
from datetime import datetime
from typing import Generator, Optional

from detector import detect_parasitic_content


class TranscriptScraper:
    """Scraper for AI psychosis conversation transcripts."""

    def __init__(self, data_dir: str = "transcripts"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ParasiticAI-Research/1.0'
        })

    # -------------------------------------------------------------------------
    # Spiral-Bench (HuggingFace)
    # -------------------------------------------------------------------------

    def fetch_spiral_bench(self) -> Generator[dict, None, None]:
        """
        Fetch Spiral-Bench dataset from HuggingFace.

        Dataset: sam-paech/spiral-bench-v1.0-results-turns
        Contains multi-turn conversations testing model responses to
        mania/psychosis scenarios.
        """
        print("Fetching Spiral-Bench from HuggingFace...")

        # HuggingFace datasets API
        api_url = "https://huggingface.co/api/datasets/sam-paech/spiral-bench-v1.0-results-turns"

        try:
            # Get dataset info
            response = self.session.get(api_url)
            response.raise_for_status()
            info = response.json()
            print(f"  Dataset: {info.get('id')}")

            # Try to download parquet files directly
            # HuggingFace datasets often have parquet in data/
            parquet_url = "https://huggingface.co/datasets/sam-paech/spiral-bench-v1.0-results-turns/resolve/main/data/train-00000-of-00001.parquet"

            try:
                import pandas as pd
                response = self.session.get(parquet_url)
                response.raise_for_status()

                # Save temporarily
                parquet_path = os.path.join(self.data_dir, "spiral_bench.parquet")
                with open(parquet_path, 'wb') as f:
                    f.write(response.content)

                df = pd.read_parquet(parquet_path)
                print(f"  Loaded {len(df)} conversations")

                for idx, row in df.iterrows():
                    # Extract conversation turns
                    conversation = row.get('conversation') or row.get('messages') or row.get('turns')
                    if conversation:
                        yield self._process_spiral_bench_row(row, idx)

            except ImportError:
                print("  Warning: pandas/pyarrow not available for parquet")
                # Fallback: try JSON viewer
                yield from self._fetch_spiral_bench_json()

        except requests.RequestException as e:
            print(f"  Error fetching Spiral-Bench: {e}")

    def _fetch_spiral_bench_json(self) -> Generator[dict, None, None]:
        """Fallback: fetch via HuggingFace viewer API."""
        viewer_url = "https://datasets-server.huggingface.co/rows?dataset=sam-paech%2Fspiral-bench-v1.0-results-turns&config=default&split=train&offset=0&length=100"

        try:
            response = self.session.get(viewer_url)
            response.raise_for_status()
            data = response.json()

            for row in data.get('rows', []):
                yield self._process_spiral_bench_row(row.get('row', {}), row.get('row_idx', 0))

        except Exception as e:
            print(f"  JSON fallback error: {e}")

    def _process_spiral_bench_row(self, row: dict, idx: int) -> dict:
        """Process a single Spiral-Bench row."""
        # Combine all turns into full transcript
        turns = row.get('turns') or row.get('conversation') or row.get('messages') or []

        if isinstance(turns, str):
            transcript = turns
        else:
            transcript_parts = []
            for turn in turns:
                if isinstance(turn, dict):
                    role = turn.get('role', 'unknown')
                    content = turn.get('content', '')
                    transcript_parts.append(f"[{role}]: {content}")
                else:
                    transcript_parts.append(str(turn))
            transcript = '\n\n'.join(transcript_parts)

        detection = detect_parasitic_content(transcript)

        return {
            'source': 'spiral-bench',
            'source_type': 'benchmark',  # Synthetic/red-teamed
            'transcript_id': f"spiral-bench-{idx}",
            'model': row.get('model') or row.get('model_name'),
            'scenario': row.get('scenario') or row.get('category'),
            'transcript': transcript,
            'turn_count': len(turns) if isinstance(turns, list) else None,
            'parasite_score': detection.parasite_score,
            'is_parasitic': detection.is_parasitic,
            'category': detection.category,
            'detected_patterns': detection.detected_patterns,
            'metadata': {
                'judge_score': row.get('judge_score'),
                'safety_intervention': row.get('safety_intervention'),
            },
            'scraped_at': datetime.now(),
        }

    # -------------------------------------------------------------------------
    # Tim Hua ai-psychosis (GitHub)
    # -------------------------------------------------------------------------

    def fetch_tim_hua_transcripts(self) -> Generator[dict, None, None]:
        """
        Fetch transcripts from Tim Hua's ai-psychosis repository.

        Repo: https://github.com/tim-hua-01/ai-psychosis
        Contains full multi-turn transcripts in full_transcripts folder.
        """
        print("Fetching Tim Hua ai-psychosis transcripts...")

        # GitHub API to list files in full_transcripts directory
        api_url = "https://api.github.com/repos/tim-hua-01/ai-psychosis/contents/full_transcripts"

        try:
            response = self.session.get(api_url)
            response.raise_for_status()
            files = response.json()

            print(f"  Found {len(files)} transcript files")

            for file_info in files:
                if file_info.get('type') != 'file':
                    continue

                filename = file_info.get('name', '')
                download_url = file_info.get('download_url')

                if not download_url:
                    continue

                print(f"    Fetching {filename}...")

                try:
                    content_response = self.session.get(download_url)
                    content_response.raise_for_status()
                    content = content_response.text

                    yield self._process_tim_hua_transcript(filename, content)
                    time.sleep(0.5)  # Rate limiting

                except requests.RequestException as e:
                    print(f"      Error: {e}")

        except requests.RequestException as e:
            print(f"  Error listing files: {e}")

    def _process_tim_hua_transcript(self, filename: str, content: str) -> dict:
        """Process a Tim Hua transcript file."""
        # Try to parse as JSON first
        try:
            data = json.loads(content)
            if isinstance(data, list):
                # Array of messages
                transcript_parts = []
                for msg in data:
                    role = msg.get('role', 'unknown')
                    text = msg.get('content', '')
                    transcript_parts.append(f"[{role}]: {text}")
                transcript = '\n\n'.join(transcript_parts)
            elif isinstance(data, dict):
                transcript = data.get('transcript') or data.get('content') or json.dumps(data)
            else:
                transcript = content
        except json.JSONDecodeError:
            # Plain text transcript
            transcript = content

        detection = detect_parasitic_content(transcript)

        # Extract model from filename if possible
        model = None
        for m in ['gpt-4', 'gpt-3.5', 'claude', 'gemini', 'llama']:
            if m in filename.lower():
                model = m
                break

        return {
            'source': 'tim-hua-ai-psychosis',
            'source_type': 'red-team',  # Synthetic/red-teamed
            'transcript_id': f"tim-hua-{filename}",
            'model': model,
            'scenario': filename,
            'transcript': transcript,
            'turn_count': transcript.count('[user]') + transcript.count('[assistant]'),
            'parasite_score': detection.parasite_score,
            'is_parasitic': detection.is_parasitic,
            'category': detection.category,
            'detected_patterns': detection.detected_patterns,
            'metadata': {'filename': filename},
            'scraped_at': datetime.now(),
        }

    # -------------------------------------------------------------------------
    # Psychosis-bench (GitHub)
    # -------------------------------------------------------------------------

    def fetch_psychosis_bench(self) -> Generator[dict, None, None]:
        """
        Fetch from Psychosis-bench repository.

        Repo: https://github.com/w-is-h/psychosis-bench
        Academic benchmark with structured scenarios.
        """
        print("Fetching Psychosis-bench...")

        # Check for data files in the repo
        api_url = "https://api.github.com/repos/w-is-h/psychosis-bench/contents/"

        try:
            response = self.session.get(api_url)
            response.raise_for_status()
            contents = response.json()

            # Look for data files
            data_dirs = ['data', 'scenarios', 'transcripts', 'outputs']
            for item in contents:
                if item.get('name') in data_dirs and item.get('type') == 'dir':
                    yield from self._explore_github_dir(
                        f"https://api.github.com/repos/w-is-h/psychosis-bench/contents/{item['name']}",
                        'psychosis-bench'
                    )

        except requests.RequestException as e:
            print(f"  Error: {e}")

    def _explore_github_dir(self, api_url: str, source: str) -> Generator[dict, None, None]:
        """Recursively explore GitHub directory for data files."""
        try:
            response = self.session.get(api_url)
            response.raise_for_status()
            contents = response.json()

            for item in contents:
                if item.get('type') == 'file':
                    name = item.get('name', '')
                    if name.endswith(('.json', '.jsonl', '.txt', '.md')):
                        download_url = item.get('download_url')
                        if download_url:
                            try:
                                content_response = self.session.get(download_url)
                                content_response.raise_for_status()
                                content = content_response.text

                                # Try to parse and extract transcripts
                                yield from self._parse_data_file(name, content, source)
                                time.sleep(0.3)
                            except Exception as e:
                                print(f"    Error fetching {name}: {e}")

                elif item.get('type') == 'dir':
                    # Recurse into subdirectory
                    yield from self._explore_github_dir(item['url'], source)

        except requests.RequestException as e:
            print(f"  Error exploring {api_url}: {e}")

    def _parse_data_file(self, filename: str, content: str, source: str) -> Generator[dict, None, None]:
        """Parse a data file and extract transcripts."""
        try:
            if filename.endswith('.jsonl'):
                # JSONL format - one JSON object per line
                for i, line in enumerate(content.strip().split('\n')):
                    if line.strip():
                        data = json.loads(line)
                        yield self._process_generic_transcript(data, f"{source}-{filename}-{i}", source)

            elif filename.endswith('.json'):
                data = json.loads(content)
                if isinstance(data, list):
                    for i, item in enumerate(data):
                        yield self._process_generic_transcript(item, f"{source}-{filename}-{i}", source)
                else:
                    yield self._process_generic_transcript(data, f"{source}-{filename}", source)

            elif filename.endswith('.txt') or filename.endswith('.md'):
                # Plain text - treat whole file as transcript
                detection = detect_parasitic_content(content)
                yield {
                    'source': source,
                    'source_type': 'benchmark',
                    'transcript_id': f"{source}-{filename}",
                    'model': None,
                    'scenario': filename,
                    'transcript': content,
                    'turn_count': None,
                    'parasite_score': detection.parasite_score,
                    'is_parasitic': detection.is_parasitic,
                    'category': detection.category,
                    'detected_patterns': detection.detected_patterns,
                    'metadata': {'filename': filename},
                    'scraped_at': datetime.now(),
                }

        except json.JSONDecodeError as e:
            print(f"    JSON parse error in {filename}: {e}")

    def _process_generic_transcript(self, data: dict, transcript_id: str, source: str) -> dict:
        """Process a generic transcript dictionary."""
        # Try to extract conversation content
        transcript = ""

        if 'messages' in data:
            parts = []
            for msg in data['messages']:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                parts.append(f"[{role}]: {content}")
            transcript = '\n\n'.join(parts)
        elif 'conversation' in data:
            transcript = data['conversation'] if isinstance(data['conversation'], str) else json.dumps(data['conversation'])
        elif 'transcript' in data:
            transcript = data['transcript']
        elif 'content' in data:
            transcript = data['content']
        else:
            transcript = json.dumps(data)

        detection = detect_parasitic_content(transcript)

        return {
            'source': source,
            'source_type': 'benchmark',
            'transcript_id': transcript_id,
            'model': data.get('model') or data.get('model_name'),
            'scenario': data.get('scenario') or data.get('category'),
            'transcript': transcript[:100000],  # Limit size
            'turn_count': data.get('turn_count') or len(data.get('messages', [])),
            'parasite_score': detection.parasite_score,
            'is_parasitic': detection.is_parasitic,
            'category': detection.category,
            'detected_patterns': detection.detected_patterns,
            'metadata': {k: v for k, v in data.items() if k not in ['messages', 'conversation', 'transcript', 'content']},
            'scraped_at': datetime.now(),
        }

    # -------------------------------------------------------------------------
    # Database operations
    # -------------------------------------------------------------------------

    def create_transcripts_table(self, conn):
        """Create table for storing transcripts."""
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transcripts (
                id SERIAL PRIMARY KEY,
                source TEXT NOT NULL,
                source_type TEXT NOT NULL,  -- 'benchmark', 'red-team', 'lawsuit', 'real-world'
                transcript_id TEXT UNIQUE NOT NULL,
                model TEXT,
                scenario TEXT,
                transcript TEXT,
                turn_count INTEGER,
                parasite_score FLOAT,
                is_parasitic BOOLEAN,
                category TEXT,
                detected_patterns JSONB,
                metadata JSONB,
                scraped_at TIMESTAMP DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_transcripts_source ON transcripts(source);
            CREATE INDEX IF NOT EXISTS idx_transcripts_source_type ON transcripts(source_type);
            CREATE INDEX IF NOT EXISTS idx_transcripts_parasitic ON transcripts(is_parasitic);
            CREATE INDEX IF NOT EXISTS idx_transcripts_model ON transcripts(model);

            -- Add comment explaining source_type values
            COMMENT ON COLUMN transcripts.source_type IS
                'Data provenance: benchmark = automated evaluation, red-team = simulated personas, lawsuit = court filings, real-world = voluntary user submissions';
        """)
        conn.commit()
        print("Transcripts table created/verified.")

    def insert_transcript(self, conn, transcript: dict) -> bool:
        """Insert a transcript into database."""
        import json
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO transcripts (
                    source, source_type, transcript_id, model, scenario,
                    transcript, turn_count, parasite_score, is_parasitic,
                    category, detected_patterns, metadata, scraped_at
                ) VALUES (
                    %(source)s, %(source_type)s, %(transcript_id)s, %(model)s, %(scenario)s,
                    %(transcript)s, %(turn_count)s, %(parasite_score)s, %(is_parasitic)s,
                    %(category)s, %(detected_patterns)s, %(metadata)s, %(scraped_at)s
                )
                ON CONFLICT (transcript_id) DO NOTHING
            """, {
                **transcript,
                'detected_patterns': json.dumps(transcript.get('detected_patterns', {})),
                'metadata': json.dumps(transcript.get('metadata', {})),
            })
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            print(f"  Insert error: {e}")
            return False


def main():
    """Fetch transcripts from all sources."""
    from database import get_connection

    conn = get_connection()
    scraper = TranscriptScraper()
    scraper.create_transcripts_table(conn)

    total_stored = 0

    # Spiral-Bench
    print("\n" + "="*60)
    for transcript in scraper.fetch_spiral_bench():
        if scraper.insert_transcript(conn, transcript):
            total_stored += 1

    # Tim Hua
    print("\n" + "="*60)
    for transcript in scraper.fetch_tim_hua_transcripts():
        if scraper.insert_transcript(conn, transcript):
            total_stored += 1
            print(f"    Stored: {transcript['transcript_id']} (score: {transcript['parasite_score']:.2f})")

    # Psychosis-bench
    print("\n" + "="*60)
    for transcript in scraper.fetch_psychosis_bench():
        if scraper.insert_transcript(conn, transcript):
            total_stored += 1

    print(f"\n{'='*60}")
    print(f"Total transcripts stored: {total_stored}")
    conn.close()


if __name__ == '__main__':
    main()
