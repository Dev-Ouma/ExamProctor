# Moodle matching OUK OpenLearn (open.ac.ke): 4.5.1+ weekly build 20250131 on PHP 8.1.
FROM php:8.1-apache-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        git libpq-dev libicu-dev libzip-dev libpng-dev libjpeg-dev libfreetype6-dev \
        libxml2-dev postgresql-client locales unzip \
    && sed -i -e 's/# en_AU.UTF-8/en_AU.UTF-8/' -e 's/# en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen && locale-gen \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j"$(nproc)" pgsql intl zip gd soap opcache exif \
    && rm -rf /var/lib/apt/lists/*

RUN { echo 'max_input_vars=5000'; echo 'memory_limit=512M'; echo 'upload_max_filesize=64M'; \
      echo 'post_max_size=64M'; } > /usr/local/etc/php/conf.d/moodle.ini

# Last MOODLE_405_STABLE commit on or before 31 Jan 2025 = build 20250131.
ARG MOODLE_BUILD_DATE=2025-02-01
RUN git clone --branch MOODLE_405_STABLE --single-branch --shallow-since=2025-01-15 \
        https://github.com/moodle/moodle.git /var/www/html.src \
    && cd /var/www/html.src \
    && git checkout -q "$(git rev-list -1 --before="${MOODLE_BUILD_DATE}" HEAD)" \
    && rm -rf .git /var/www/html && mv /var/www/html.src /var/www/html \
    && mkdir -p /var/moodledata && chown -R www-data:www-data /var/www/html /var/moodledata

COPY config.php /var/www/html/config.php
COPY entrypoint.sh /usr/local/bin/moodle-entrypoint
RUN chmod +x /usr/local/bin/moodle-entrypoint
ENTRYPOINT ["moodle-entrypoint"]
CMD ["apache2-foreground"]
