# Security and Backups

## Authentication design

The company code and password register a store installation. Each employee then signs in with an individual PIN. PINs are stored on the server as salted PBKDF2-SHA256 hashes; the plaintext PIN is never stored. A successful offline login is possible only after that employee has completed an online login on that computer.

The Windows configuration contains a long-lived company connection token in the signed-in user's local application-data folder. Windows computers should therefore use individual Windows accounts, disk encryption, automatic screen locking, current antivirus protection, and restricted administrator access.

## Role enforcement

The server checks the employee's current active status and role on every protected request. Changing or disabling a user centrally prevents new server changes even if an older desktop screen is still open. During a total outage, the client cannot learn about a newly disabled employee until connectivity returns; this is an inherent tradeoff of offline operation.

## Network requirements

- Use HTTPS for every production client.
- Do not forward PostgreSQL port 5432 to the internet.
- Do not expose API port 8000 publicly.
- Allow public access only through the included HTTPS gateway on ports 80/443.
- Restrict server SSH/administration access by firewall and key-based authentication.
- Apply operating-system and container updates on a regular maintenance schedule.

## Database backups

The PostgreSQL volume survives normal container replacement, but a volume is not a backup. Keep backups on a different system or storage provider.

To create an encrypted-transfer-ready compressed database dump from the server:

```text
sh server/backup_database.sh
```

An optional destination can be supplied:

```text
sh server/backup_database.sh /secure/backup/path
```

Recommended policy:

- Daily automated PostgreSQL backup
- At least 30 daily restore points
- At least 12 monthly restore points
- One copy outside the server/provider
- Quarterly test restoration into a non-production database
- Backup before every application update or bulk import

## Restore outline

1. Stop desktop changes or place the server into maintenance mode.
2. Create a final backup of the current database, even if damaged.
3. Restore the selected dump into a fresh PostgreSQL database.
4. Start the API and verify `/api/health`.
5. Test company and employee sign-in.
6. Check customer count, active-order count, and store reports.
7. Reopen the service to store clients.

Practice this procedure before an emergency. A backup is only proven after a successful restoration test.

## Customer information

The system is designed for ordinary customer/contact and print-production details. Do not store payment-card numbers, government identification images, passwords, medical records, or other regulated sensitive information in customer/order notes or artwork-path fields.

