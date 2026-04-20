FROM php:7.4-apache

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libfreetype6-dev \
        libjpeg62-turbo-dev \
        libpng-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j4 gd mysqli pdo_mysql \
    && rm -rf /var/lib/apt/lists/*

RUN a2enmod rewrite \
    && sed -i '/<Directory \/var\/www\/>/,/<\/Directory>/ s/AllowOverride None/AllowOverride All/' /etc/apache2/apache2.conf

RUN printf "%s\n" \
    "allow_url_fopen = On" \
    "allow_url_include = On" \
    "display_errors = On" \
    "display_startup_errors = On" \
    > /usr/local/etc/php/conf.d/pikachu.ini

COPY pikachu-src/ /var/www/html/

RUN sed -i "s/define('DBHOST', '127.0.0.1');/define('DBHOST', 'db');/" /var/www/html/inc/config.inc.php \
    && sed -i "s/define('DBPW', '');/define('DBPW', 'pikachu');/" /var/www/html/inc/config.inc.php \
    && sed -i "s/define('DBHOST', 'localhost');/define('DBHOST', 'db');/" /var/www/html/pkxss/inc/config.inc.php \
    && sed -i "s/define('DBPW', 'root');/define('DBPW', 'pikachu');/" /var/www/html/pkxss/inc/config.inc.php

RUN chown -R www-data:www-data /var/www/html

EXPOSE 80
