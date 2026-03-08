# 📝 Skill-Bridge Career Navigator

**Candidate Name:** Brandon Sanchez

**Scenario Chosen:** 2 — Skill-Bridge Career Navigator

**Estimated Time Spent:** ~5.5 hours

---

## Quick Start

- **Prerequisites:** Python 3.11+, pip
- **Run Commands:**
  ```bash
  python -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  
  # if you want to use the APIs please insert the openAI and RapidAPI (for JSearch) into the env file
  # if you don't want to use the APIs then it will revert to the synthetic data as fallback
  cp .env.example .env 
  
  # runs on http://localhost:5000
  python app.py
  # or 
  flask run
  ```
- **Test Commands:**
  ```bash
  python -m pytest tests/
  ```

---

## AI Disclosure

- **Did you use an AI assistant (Copilot, ChatGPT, etc.)?** Yes
- **How did you verify the suggestions?**
  I cross-referenced the AI suggestions against like the official documentation and my own prior experience with some of these libraries that I for this project. For API calls and such I did my best to find the latest documentation as from prior experience working with AI, sometimes the code suggestion in terms of like API calls can be out of date.
- **Give one example of a suggestion you rejected or changed:**
  So to just briefly explain, like I've mentioned previously from my experience something Claude for example will suggest outdated API syntax. So for example, for this project it kept suggesting to use `chat.completions.create()` when integrating with the OpenAI API. However, having worked with the API before, I knew that OpenAI now recommends using `client.responses.create()` instead, as it is more flexible and better supported going forward and moreover Claude had also suggested to pass in parameters for `temperature` and `presence_penalty`,  but with the newer GPT models (more specifically GPT-5) no longer support those parameters. So Claude code for was suggesting older API documentation that did not apply to what I was trying to accomplish as I was trying to work with `gpt-5-mini`. 

---

## Tradeoffs & Prioritization

- **What did you cut to stay within the 4–6 hour limit?**
  I would have liked to add some sort of authentication and better user accounts because as of right now, the profiles are accessible via simple sequential IDs (e.g., `/profile/1`, `/profile/2`), which means anyone could essentially view another person's skills and personalized roadmap. In obviously, in a production scenario this would need proper auth, but I chose to ship a functional MVP within the time constraint instead just because I felt it would have taken me a while to implement whereas I could instead mainly focus on the core of the case scenario that I am trying to solve.
- **What would you build next if you had more time?**
 Like I mentioned previously, I would have like to have full authentication system with user registration and login. Passwords would be hashed with salt before storing in the database, and login would compare the hashed input against the stored hash. Each user would essentially only be able to view and manage their own profile. I would also replace the sequential integer IDs with UUIDs to make profile endpoints harder to enumerate. I would have also like to add more personalized analysis depending on the persona the user chooses. For example, as of right now, the only persona that as some unique personalization to it is the career switcher which in which it shows like a "transferable skills" section that I think is unique to that persona. So adding other unique features to each persona would be something I would like to add.
- **Known limitations:**
  - No authentication
  - Skill detection in job postings relies on a hardcoded regex dictionary, so skills not in that list are missed. I tried my best to incorporate skills from a variety of jobs however I might now have gotten them all.
  - The app works fully offline with fallback data, but the gap analysis and roadmap are more generic without API keys
  - The loading of the profile, gap analysis, and roadmap might take a little bit to load. There are times when testing where it might hang for a while.