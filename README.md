# hackerrank_submissions_scorer

This is a rudimentary HackerRank scoring script written originally for use at Glasgow University Tech Society's Code Olympics 2025 hackathon.

Currently only works for macOS.

This takes all submissions from the JSON at <https://www.hackerrank.com/rest/contests/contest-slug/judge_submissions/?offset=0&limit=10000> and collates them on a user, challenge, and team basis, with the aid of a CSV of usernames collected from participants (to know who is in which team). The correct functioning of this script relies on this data being correct and ideally cleaned before usage.
