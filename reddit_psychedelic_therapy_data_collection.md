# Reddit Data Collection: Real-World Psychedelic Therapy Experiences

## Project Overview
Exploratory data collection to assess feasibility of studying patient-reported experiences with legal psychedelic-assisted therapy through Reddit posts.

## Objective
Collect preliminary data from Reddit to determine:
1. Volume of relevant posts discussing real-world psychedelic therapy experiences
2. Quality and detail of information shared
3. Geographic distribution (Oregon, Colorado, Australia, etc.)
4. Types of experiences reported (positive/negative outcomes, acute experiences, service quality)

## Target Subreddits
Primary subreddits to search:
- r/psychedelics
- r/Psychonaut
- r/TherapeuticKetamine
- r/PsilocybinMushrooms
- r/mdmatherapy
- r/AustralianPsychedelic (if exists)
- r/oregon (for psilocybin services)
- r/Colorado (for natural medicine programs)

## Search Keywords/Phrases
Use combinations of these terms to identify relevant posts:

**Treatment Settings:**
- "psilocybin therapy"
- "psychedelic therapy"
- "facilitated session"
- "licensed facilitator"
- "service center"
- "therapy center"
- "Oregon psilocybin"
- "Colorado psychedelic"
- "Australian psychiatrist"
- "legal psilocybin"
- "legal psychedelic therapy"

**Experience Descriptors:**
- "my session"
- "my experience with"
- "just completed"
- "therapy session"
- "integration"
- "preparation"

## Data Fields to Extract

For each relevant post, collect:

### Post Metadata
- Post ID
- Subreddit
- Date posted
- Username (anonymized/hashed)
- Title
- Full text content
- Number of upvotes
- Number of comments
- Post flair (if available)

### Content Variables (to be coded/extracted manually or via NLP later)
Note which of these elements are present in posts:
- Geographic location/jurisdiction mentioned (Oregon, Colorado, Australia, etc.)
- Type of substance (psilocybin, MDMA, LSD, ketamine, etc.)
- Treatment setting (clinical trial, service center, therapeutic setting, other)
- Clinical indication mentioned (depression, PTSD, anxiety, other)
- Outcome description (positive/negative, specific domains)
- Acute experience description (challenging/difficult, positive/mystical)
- Service quality mentions (facilitator/therapist, setting, preparation, integration)
- Cost mentioned
- Legal status clarity (clearly legal vs. unclear)

## Time Frame
- Collect posts from the past **2 years** (January 2023 - present)
- This captures the period after Oregon's psilocybin program launched (2023)

## Output Format
Deliver data as:
1. **CSV file** with post metadata and full text
2. **Summary statistics document** including:
   - Total posts collected per subreddit
   - Date range of posts
   - Top keywords found
   - Preliminary count of posts mentioning specific jurisdictions
   - Sample of 10-20 representative post excerpts

## Technical Requirements
- Use Reddit API (PRAW library recommended for Python)
- Respect Reddit's API rate limits
- Ensure data collection complies with Reddit's Terms of Service
- Remove or hash any personally identifying information
- Save raw data with timestamps of collection

## Sample Size Target
Aim to collect:
- Minimum: 100 relevant posts
- Target: 500+ relevant posts
- Include top-level comments on highly relevant posts (optional for preliminary phase)

## Exclusion Criteria
Filter out posts that are:
- Clearly about underground/illegal experiences
- Purely about recreational use
- Asking questions rather than describing experiences
- About growing mushrooms or cultivation
- Spam or promotional content

## Deliverables
1. CSV file with collected data
2. Brief summary report (1-2 pages) with:
   - Feasibility assessment
   - Data quality notes
   - Preliminary themes observed
   - Recommendations for full data collection
3. Code used for data collection (Python script)

## Timeline
Preliminary data collection: 1-2 weeks

## Questions/Clarifications Needed
Please reach out if:
- Reddit API access issues arise
- Search terms yield insufficient results
- Additional subreddits should be included
- Specific data fields need clarification

## Contact
Cooper Tretter - coopertretter@gmail.com
