# Conservative Clinic Case Registration — Prototype

## Features
- 541 students imported with Student ID, Group, Subgroup.
- Conservative cases: Operative (Class II, III, IV, V, Direct Veneer) and Endodontics (Single Canal, Two Canals).
- Multiple requirements can be recorded in one case entry.
- Palmer notation: quadrant + tooth number 1–8.
- Strict 7-day submission rule from case date.
- Admin exceptions: student, subgroup, group, or all students.
- Admin case overview.

## Run
1. Install Python 3.11+.
2. `pip install -r requirements.txt`
3. `python import_students.py`
4. Set a real admin password before production: `ADMIN_PASSWORD=...`
5. `python app.py`
6. Open `http://127.0.0.1:5000`

Prototype admin password: `admin123` (change before any real use).

## Important before real deployment
This prototype stores patient names, so production hosting must use authentication, HTTPS, access controls, backups, and an appropriate privacy/data-retention policy. File uploads are not enabled in this first build.

## Student accounts
- Each student has a unique username (same as Student ID) and a random password.
- The administration-only file `student_credentials.xlsx` contains the initial credentials for all 541 students.
- Passwords stored in `clinic.db` are PBKDF2 hashes, not plaintext.
- Admin can generate a new password for a student from the Admin Dashboard.
