# Deployment Guide

This guide separates the one-time server deployment from the installation performed at each store.

## 1. Choose the central server

For production, use a reliable cloud virtual machine or container host with:

- A public IP address
- A domain or subdomain, such as `orders.yourdomain.com`
- Docker and Docker Compose
- At least 2 GB RAM
- Persistent disk storage
- Inbound ports 80 and 443
- Automated server snapshots or an external backup destination

A computer inside one store is acceptable for testing, but it is a poor production server: power loss, router changes, Windows updates, or store internet outages would disconnect every location.

## 2. Configure DNS and HTTPS

Create an `A` record for the chosen domain pointing to the server's public IP address. The included Caddy gateway automatically requests and renews HTTPS certificates once DNS is correct and ports 80/443 reach the server.

Never expose the internal API or PostgreSQL port directly to the internet. Store clients should connect only to the HTTPS address.

## 3. Create secure environment settings

On the server, copy `server/.env.example` to `.env` in the project root. Replace every placeholder.

Generate a JWT secret with:

```text
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Recommended values:

- `POSTGRES_PASSWORD`: at least 24 URL-safe random characters (letters, numbers, `-`, and `_`)
- `JWT_SECRET`: output of the command above
- `BOOTSTRAP_COMPANY_CODE`: a short internal code employees can recognize
- `BOOTSTRAP_COMPANY_PASSWORD`: a unique password not used anywhere else
- `BOOTSTRAP_ADMIN_PIN`: at least six digits; avoid birthdays and store numbers
- `SITE_ADDRESS`: the full HTTPS domain, such as `https://orders.yourdomain.com`

The bootstrap values create the company, three locations, and first administrator only when the database is empty. Changing them later does not overwrite the live database.

## 4. Start the server

From the project root:

```text
docker compose up -d --build
docker compose ps
```

Confirm the public address responds:

```text
https://orders.yourdomain.com/api/health
```

The response should contain `"status":"ok"`.

The interactive API reference is available at `/api/docs`. It does not bypass authentication.

## 5. Build the Windows installer

On a Windows 11 computer with Python 3 installed:

1. Open the `client` folder.
2. Double-click `build_windows_exe.bat`.
3. Confirm `client\dist\PrintOrderManager-MultiStore.exe` was created.
4. Install Inno Setup if a full installer is desired.
5. Open and compile `installer\PrintOrderManager.iss`.
6. The finished installer will be in `installer\output`.

Alternatively, place the project in a private GitHub repository and run the included **Build Windows Installer** workflow. Download the resulting private build artifact. Do not publish an installer containing business configuration or customer data.

## 6. Install at each store

Run the installer once on each approved Windows computer. At first launch:

1. Enter the public HTTPS server address.
2. Enter the shared company code and password.
3. Select the computer's store location.
4. Select the administrator and enter the administrator PIN.
5. Open **Employees** and add the store staff.

The shared company password connects the installation. Employees then use their own PINs for identity, permissions, and activity tracking.

## 7. Add employee access

Administrators can create employees with one or more assigned stores.

| Role | Intended access |
| --- | --- |
| Employee | Customers, new orders, line items, production changes, printing |
| Supervisor | Employee capabilities plus deletion, store reports, and conflict override |
| Administrator | All stores, all reports, employee access, deletion, and conflict override |

Use a separate employee profile for each person. Do not have multiple people share an employee PIN.

## 8. Import the original application

Import from the computer containing the existing local database:

1. Install and connect the multi-store client first.
2. Close both applications.
3. Back up `%LOCALAPPDATA%\PrintOrderManager\print_orders.db`.
4. Open the new `client` folder and double-click `import_legacy.bat`.
5. Enter the store number that owns those orders.
6. Open the multi-store client as a Supervisor or Administrator and click **Sync Now**.
7. Confirm order counts before removing the old application.

The importer refuses to import the exact same database twice on the same computer.

## 9. Rollout order

Use this sequence to reduce duplicate or conflicting data:

1. Deploy and test the server.
2. Configure the Administrator and employee profiles.
3. Back up every old store database.
4. Import one store at a time and allow synchronization to finish.
5. Verify customers, active orders, totals, and reports.
6. Install the client on remaining workstations.
7. Make the old system read-only after sign-off.

Do not run the old and new systems as separate live order systems after migration.
