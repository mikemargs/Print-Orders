# Customer Issues — design

## Approved purpose and scope

Add a Customer Issues section to the existing Print Order Manager website for Sayville (#5127), Selden (#5345), and Mt. Sinai (#3167). Employees need one shared record of complaints, complications, communications, updated information, follow-ups, and resolutions. The user approved integration with the existing website and manual communication logging only.

Success means an employee can open a case, record contact with a customer, assign a next action and due date, and another employee can understand and continue the case. Open and overdue cases remain visible across stores. Cases can be resolved and reopened while preserving history.

## Integration and approach

Extend the existing React/TypeScript frontend, FastAPI services, SQLAlchemy database, and Alembic migrations. Reuse company login, employee PIN sessions, CSRF protection, customer records, store selection, and The UPS Store blue styling. No separate deployment or authentication system is needed.

A separate website would duplicate customer records and administration. Using GitHub Issues as the case database would introduce another staff workflow and a different access model. The integrated database-backed section best fits the approved goal.

## Screens and workflow

- Add Customer Issues to the main navigation. Its landing page shows open, overdue, high-priority, and assigned-to-me counts plus a paginated case list. Filters include store, status, priority, category, assignee, and customer/name/case-reference search. Default view includes all unresolved cases across company stores.
- Add a compact open/overdue issues summary linking from Main Dashboard; retain its existing pending-order view.
- New case form: select an existing customer or use the existing customer-creation flow, select store, enter title and description, choose category and priority, optionally assign an employee and link a print order, and enter next action/follow-up date.
- Case detail: editable case information, customer contact details, optional work-order link, and chronological history. Show the case version and latest update through normal conflict handling rather than technical fields in the form.
- Add communication form: channel, occurrence date/time, summary, and optional next action/follow-up date update. Channels: phone, email, in person, internal note, other. Logging an email records a communication; it does not send anything.
- Resolve requires a nonblank resolution summary. Reopen requires a reason. Both create history entries. Editing customer contact information uses the existing customer editor.

Categories: Shipping, Print Order, Mailbox, Billing/Refund, Customer Service, Other. Priorities: Low, Normal, High, Urgent. Statuses: Open, In Progress, Waiting on Customer, Waiting on Third Party, Resolved. Every status except Resolved counts as open.

## Data model

CustomerIssue stores UUID, company, customer, store, human-readable reference, title, description, category, priority, status, optional employee assignment, optional work-order link, next action, nullable follow-up date, resolution summary, version, creator/updater, and creation/update/resolution timestamps. Allocate a unique case reference server-side and enforce uniqueness within the company. Assignment uses employee IDs rather than names.

IssueActivity stores UUID, company, case ID, activity type (communication or case change), channel when applicable, occurred-at timestamp, recorded-at timestamp, author employee ID, author name snapshot, text summary, structured changed fields for system entries, and a unique client-generated operation ID. Communication entries are append-only; corrections are new notes referencing the original. Server-generated changes record status, priority, assignment, description, store, links, and follow-up changes.

Add indexes for company/store/status, follow-up date, customer, assignee, case reference, and case timeline. The migration is additive and does not modify existing orders or customers.

## API and consistency

Add a dedicated issue router and issue service. Endpoints cover paginated filtered lists, full-set summary counts, create, detail, versioned patch, activity list, and communication append. Resolve/reopen use explicit service validation through versioned patch requests. Responses include customer, store, and employee display information needed by the screens without returning unrelated customer records.

Lists have bounded pagination and totals; summaries calculate over the complete matching dataset, not just the current page. Case updates and their audit entries commit atomically. Version checks use an atomic conditional update so concurrent edits return HTTP 409 with the current case instead of overwriting it. Communication operation IDs prevent duplicate entries on a retry. A log that also updates the next action/follow-up checks the supplied case version and commits both changes together.

Validate lengths and enums, real dates, active company stores and assignees, customer ownership, and linked-order ownership/customer/store matching. Changing customer or store requires clearing an incompatible order link. Customer issues do not participate in the legacy desktop sync feed; desktop behavior remains unchanged.

## Access and dates

Signed-in employees can read the company-wide case list and histories, consistent with the existing all-store order dashboard. Employees can create/update/log/resolve/reopen only cases at their active store, subject to the existing store-assignment checks. Administrators can work across company stores. Assignees must be active company employees eligible for the selected store. Author identity is derived from the server session; clients cannot impersonate another employee. No hard-delete action is exposed.

All reads and writes enforce company isolation on the server. Writes use existing CSRF/session dependencies. Store switches invalidate case queries. Clear cached query data on logout or identity change.

Follow-up is a date in the case store's timezone (America/New_York for the current stores). Overdue means unresolved with a follow-up date earlier than the store's current date; today's cases are due today. Communication timestamps are stored in UTC and displayed in the store timezone. Historical occurrence dates are permitted; recording time remains server-generated.

## Connectivity and errors

First version requires a connection to load and edit issues. Do not add persistent offline caching of complaint histories. Existing cached-order outage behavior continues. The issues section displays an explicit offline message and disables writes while offline. Previously loaded in-memory information may remain visible with an offline/stale indicator.

Refresh lists, counts, and detail after successful changes; poll visible issue queries every 30 seconds while online and refresh on focus. Show save failures inline and preserve entered text. On a version conflict, show the current case and require review before resubmission. Provide explicit loading, empty, forbidden, not-found, and retry states; never present a failed request as an empty case list.

## Validation and release

Backend coverage verifies company isolation, active-store write restrictions, link/assignee validation, resolve/reopen history, atomic conflicts, retry deduplication, full-dataset summaries, and timezone-based overdue behavior. Frontend coverage verifies create/log/follow-up/resolve/reopen flows, filters, conflict and offline states, and navigation. Run existing backend tests, frontend tests, typecheck, lint, production build, and targeted browser end-to-end checks with fictional customers.

Deliver an isolated feature branch and reviewable pull request. Include migration and deployment instructions. Production release uses the existing migration process before the updated app serves requests. This design does not itself deploy changes or migrate production.

## Explicit limits

Manual logging only; no email sending/import, SMS, customer portal, automatic reminders, complaint attachments, or refund-payment processing in this version. Resolution notes may describe refunds or replacements without changing financial order totals.
