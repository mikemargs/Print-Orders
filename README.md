# Print Order Manager — Multi-Store Edition

A downloadable Windows desktop application backed by one central database for multiple print-store locations. The included deployment is preconfigured for:

- Sayville — Store #5127
- Selden — Store #5345
- Mt. Sinai — Store #3167

The desktop program keeps a local cache, so staff can continue creating customers and work orders during temporary internet outages. Changes automatically synchronize after connectivity returns.

## Included capabilities

- Live customer and print-order synchronization across all three stores
- Offline order entry with a visible pending-change count
- Safe retrying: each upload has a unique operation ID and cannot be applied twice
- Version-based conflict protection and a review screen
- One shared company connection plus individual employee PINs
- Employee, Supervisor, and Administrator roles
- Store assignments for employees
- Store-specific and company-wide reports
- Multiple line items, print specifications, pricing, tax, discount, deposit, and balance
- Production statuses, priorities, deadlines, employee assignment, and artwork path
- Printable work tickets that can be saved as PDF
- Legacy import from the original single-computer edition
- PostgreSQL production database, HTTPS gateway, health endpoint, and backup script
- Windows EXE and installer build files

## Project layout

| Folder | Purpose |
| --- | --- |
| `client` | Windows desktop program, local cache, offline queue, and synchronization engine |
| `server` | Secure API, authentication, conflict detection, reporting, and database models |
| `installer` | Inno Setup definition for a normal Windows installer |
| `tests` | Local-store and end-to-end API tests |
| `.github/workflows` | Optional automated Windows installer build |

## Important deployment requirement

Every store installs the Windows client, but the central server must first be deployed to an internet-accessible computer or cloud service. The server URL must use HTTPS in production. Do not copy a SQLite database into Dropbox, OneDrive, Google Drive, or a shared network folder for simultaneous use.

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for the complete setup sequence.

## Quick local demonstration

This starts the central server on one computer for testing:

1. Install Docker Desktop.
2. Copy `server/.env.example` to `.env` in this top-level folder.
3. Replace every placeholder password and secret in `.env`.
4. Leave `SITE_ADDRESS=http://localhost` for the test.
5. Run `docker compose up -d --build` from this folder.
6. Open `http://localhost/api/health`; it should show `"status":"ok"`.
7. On the same computer, open `client` and double-click `run_client.bat`.
8. Use `http://localhost` as the server address, then enter the company code/password from `.env`.

`run_client.bat` creates an isolated Python environment on first use. For employee computers, build the EXE or installer instead.

## Run tests

With the server development dependencies installed:

```text
python -m pip install -r server/requirements.txt requests httpx
python -m unittest discover -s tests -v
```

## Data locations

- Central production records: PostgreSQL volume on the server
- Windows offline cache: `%LOCALAPPDATA%\PrintOrderManagerMultiStore\multistore_cache.db`
- Windows connection settings: `%LOCALAPPDATA%\PrintOrderManagerMultiStore\client_config.json`

The local cache is not the authoritative backup. Back up the central PostgreSQL database as described in `SECURITY_AND_BACKUPS.md`.

