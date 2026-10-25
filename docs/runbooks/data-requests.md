# Data requests, legal hold and retention

## Subject access (export) and erasure

Use Moodle's Data requests (Site administration > Users > Privacy and policies). The ExamProctor
privacy provider fetches the service's data (images, events, flags, scores, decisions) with signed
calls and adds it to the export; erasure deletes it in the service too. Face templates are never
exported. If the service is unreachable the request fails and can be retried; it is never marked
done with data left behind.

## Legal hold

A session on legal hold is kept by retention and erasure (erasure reports it as held). Set it on
the service database:

    cd /opt/examproctor && sudo docker compose exec service-db psql -U examproctor -c \
      "UPDATE sessions SET legal_hold = true WHERE id = '<session id>'"

Record who asked, why and when; release with `false` when the matter closes.

## Retention

Evidence is deleted 90 days after a session ends (`EXAMPROCTOR_RETENTION_DAYS`), except on legal
hold. Flags, scores and decisions stay with the session record; the report shows "Images deleted".
