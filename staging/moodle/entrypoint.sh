#!/bin/sh
# Install Moodle on first start, then install or upgrade the ExamProctor plugins.
set -eu
cd /var/www/html

until pg_isready -q -h "$MOODLE_DB_HOST" -U "$MOODLE_DB_USER"; do
    echo "waiting for moodle-db..."; sleep 2
done

chown -R www-data:www-data /var/moodledata
installed=$(PGPASSWORD="$MOODLE_DB_PASSWORD" psql -h "$MOODLE_DB_HOST" -U "$MOODLE_DB_USER" -d "$MOODLE_DB_NAME" \
    -tAc "SELECT 1 FROM information_schema.tables WHERE table_name = 'mdl_config'")
if [ "$installed" != "1" ]; then
    su -s /bin/sh www-data -c "php admin/cli/install_database.php --agree-license \
        --fullname='ExamProctor Staging' --shortname=epstaging \
        --adminuser=admin --adminpass='$MOODLE_ADMIN_PASSWORD' --adminemail=admin@example.invalid"
fi
su -s /bin/sh www-data -c "php admin/cli/upgrade.php --non-interactive"

exec "$@"
