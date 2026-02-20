import os
import re
import csv
import requests
import browser_cookie3

# ----------------------------
# Config
# ----------------------------

CONTEST_SLUG = "code-olympics-2025"
CHROME_PROFILE = "Profile 1"   
USERS_CSV_PATH = "users.csv"

PAGE_SIZE = 1000
mods = set()       
block_list = set()  

# ----------------------------
# HackerRank API auth + fetch
# ----------------------------
def chrome_cookie_file_for_profile(profile_dir=CHROME_PROFILE):
    base = os.path.expanduser("~/Library/Application Support/Google/Chrome")
    candidate1 = os.path.join(base, profile_dir, "Network", "Cookies")
    candidate2 = os.path.join(base, profile_dir, "Cookies")
    if os.path.exists(candidate1):
        return candidate1
    if os.path.exists(candidate2):
        return candidate2
    raise FileNotFoundError(f"Could not find Cookies DB for {profile_dir}")


def make_session(contest_slug=CONTEST_SLUG, profile_dir=CHROME_PROFILE):
    contest_page_url = f"https://www.hackerrank.com/contests/{contest_slug}/"

    s = requests.Session()

    cookie_file = chrome_cookie_file_for_profile(profile_dir)
    s.cookies = browser_cookie3.chrome(cookie_file=cookie_file, domain_name="hackerrank.com")

    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://www.hackerrank.com",
        "Referer": contest_page_url,
    })

    r = s.get(contest_page_url, timeout=30)
    print("Contest page status:", r.status_code)
    r.raise_for_status()

    m = re.search(
        r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']+)["\']',
        r.text,
        re.I,
    )
    if m:
        s.headers["X-CSRF-Token"] = m.group(1)

    return s


def fetch_all_submissions(contest_slug=CONTEST_SLUG, profile_dir=CHROME_PROFILE, page_size=1000):
    session = make_session(contest_slug, profile_dir)
    all_submissions = []
    seen_submission_ids = set()

    offset = 0
    total_expected = None

    while True:
        url = (
            f"https://www.hackerrank.com/rest/contests/{contest_slug}/judge_submissions/"
            f"?offset={offset}&limit={page_size}"
        )

        resp = session.get(url, timeout=30)
        if resp.status_code == 403:
            print("403 response headers:", dict(resp.headers))
            print("403 body (first 1000 chars):", resp.text[:1000])
            raise RuntimeError("403 Forbidden while fetching judge_submissions")

        resp.raise_for_status()
        page = resp.json()

        if total_expected is None:
            print("Response keys:", list(page.keys()))
            total_expected = page.get("total")  
            print("Reported total:", total_expected)

        models = page.get("models", [])
        if not models:
            print("No models returned; stopping.")
            break

        new_count = 0
        for submission in models:
            sub_id = submission.get("id")
            if sub_id is not None:
                if sub_id in seen_submission_ids:
                    continue
                seen_submission_ids.add(sub_id)

            all_submissions.append(submission)
            new_count += 1

        print(
            f"offset={offset} got={len(models)} rows "
            f"(new={new_count}, total_collected={len(all_submissions)})"
        )

        if total_expected is not None and len(all_submissions) >= total_expected:
            print("Reached reported total; stopping.")
            break

        offset += len(models)

        if new_count == 0:
            print("Page contained no new submissions; stopping to avoid infinite loop.")
            break

    return all_submissions


# ----------------------------
# Scoring logic
# ----------------------------
def load_users_and_teams(users_csv_path=USERS_CSV_PATH):
    teams = {}
    users = {}

    with open(users_csv_path, "r", newline="") as csvfile:
        reader = csv.reader(csvfile)
        next(reader, None)  

        for row in reader:
            if not row or len(row) < 2:
                continue

            team = row[1].strip()
            if not team:
                continue

            teams.setdefault(team, {"user_data": {}, "challenges": {}})

            for person in row[2:]:
                person = person.strip()
                if not person:
                    continue

                if person in users:
                    raise ValueError(f"Duplicate username in users.csv: {person}")

                users[person] = team
                teams[team]["user_data"][person] = {}

    return teams, users


def compute_team_scores(submissions, teams, users, mods=None, block_list=None):
    if mods is None:
        mods = set()
    if block_list is None:
        block_list = set()

    team_scores = []
    ty = set()  
    grr = set()  
    huh = set() 

    for submission in submissions:
        try:
            challenge = submission["challenge"]["slug"]
            score = submission["score"]
            user = submission["hacker_username"]
        except KeyError:
            continue

        if user not in users:
            if user in mods:
                ty.add(f"mod: {user}")
            elif user in block_list:
                grr.add(f"BAN: {user}")
            else:
                huh.add(f"Missing: {user}")
            continue

        team_name = users[user]

        user_scores = teams[team_name]["user_data"][user]
        if challenge not in user_scores:
            user_scores[challenge] = score
        else:
            user_scores[challenge] = max(user_scores[challenge], score)

        team_challenge_scores = teams[team_name]["challenges"]
        if challenge not in team_challenge_scores:
            team_challenge_scores[challenge] = score
        else:
            team_challenge_scores[challenge] = max(team_challenge_scores[challenge], score)

    for team_name, team_data in teams.items():
        total = sum(team_data["challenges"].values())
        team_scores.append((team_name, round(total, 2)))

    team_scores.sort(key=lambda x: x[1], reverse=False)

    return team_scores, ty, grr, huh


def main():
    teams, users = load_users_and_teams(USERS_CSV_PATH)
    print(f"Loaded {len(users)} users across {len(teams)} teams")

    submissions = fetch_all_submissions(CONTEST_SLUG, CHROME_PROFILE, PAGE_SIZE)
    print(f"Total submissions fetched: {len(submissions)}")

    team_scores, ty, grr, huh = compute_team_scores(
        submissions, teams, users, mods=mods, block_list=block_list
    )

    print("\n--- Unknown users ---")
    print("Mods:", ty)
    print("Blocked:", grr)
    print("Missing:", huh)

    print("\n--- Team leaderboard ---")
    for rank, (team, score) in enumerate(team_scores, start=1):
        print(f"{rank}. {team}: {score}")


if __name__ == "__main__":
    main()