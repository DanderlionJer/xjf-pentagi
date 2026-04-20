"""Generate UTF-8 Docker assets (run: python write_pikachu_assets.py)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    dockerfile = "\n".join(
        [
            "FROM php:7.4-apache",
            "",
            "RUN apt-get update \\",
            "    && apt-get install -y --no-install-recommends \\",
            "        libfreetype6-dev \\",
            "        libjpeg62-turbo-dev \\",
            "        libpng-dev \\",
            "    && docker-php-ext-configure gd --with-freetype --with-jpeg \\",
            "    && docker-php-ext-install -j4 gd mysqli pdo_mysql \\",
            "    && rm -rf /var/lib/apt/lists/*",
            "",
            "RUN a2enmod rewrite \\",
            r"    && sed -i '/<Directory \/var\/www\/>/,/<\/Directory>/ s/AllowOverride None/AllowOverride All/' /etc/apache2/apache2.conf",
            "",
            "RUN printf \"%s\\n\" \\",
            '    \"allow_url_fopen = On\" \\',
            '    \"allow_url_include = On\" \\',
            '    \"display_errors = On\" \\',
            '    \"display_startup_errors = On\" \\',
            "    > /usr/local/etc/php/conf.d/pikachu.ini",
            "",
            "COPY pikachu-src/ /var/www/html/",
            "",
            "RUN sed -i \"s/define('DBHOST', '127.0.0.1');/define('DBHOST', 'db');/\" /var/www/html/inc/config.inc.php \\",
            "    && sed -i \"s/define('DBPW', '');/define('DBPW', 'pikachu');/\" /var/www/html/inc/config.inc.php \\",
            "    && sed -i \"s/define('DBHOST', 'localhost');/define('DBHOST', 'db');/\" /var/www/html/pkxss/inc/config.inc.php \\",
            "    && sed -i \"s/define('DBPW', 'root');/define('DBPW', 'pikachu');/\" /var/www/html/pkxss/inc/config.inc.php",
            "",
            "RUN chown -R www-data:www-data /var/www/html",
            "",
            "EXPOSE 80",
            "",
        ]
    )

    compose = "\n".join(
        [
            "services:",
            "  db:",
            "    image: mysql:8.0",
            "    container_name: pikachu-mysql",
            "    environment:",
            "      MYSQL_ROOT_PASSWORD: pikachu",
            "    volumes:",
            "      - pikachu_mysql_data:/var/lib/mysql",
            "      - ./init.sql:/docker-entrypoint-initdb.d/00-init.sql:ro",
            "    healthcheck:",
            '      test: ["CMD", "mysqladmin", "ping", "-h", "127.0.0.1", "-ppikachu"]',
            "      interval: 5s",
            "      timeout: 5s",
            "      retries: 30",
            "      start_period: 20s",
            "",
            "  web:",
            "    build:",
            "      context: .",
            "      dockerfile: Dockerfile",
            "    image: pikachu:local",
            "    container_name: pikachu-web",
            "    ports:",
            '      - "8765:80"',
            "    depends_on:",
            "      db:",
            "        condition: service_healthy",
            "",
            "volumes:",
            "  pikachu_mysql_data:",
            "",
        ]
    )

    init_sql = "CREATE DATABASE IF NOT EXISTS pikachu;\nCREATE DATABASE IF NOT EXISTS pkxss;\n"

    (ROOT / "Dockerfile").write_text(dockerfile, encoding="utf-8", newline="\n")
    (ROOT / "docker-compose.yml").write_text(compose, encoding="utf-8", newline="\n")
    (ROOT / "init.sql").write_text(init_sql, encoding="utf-8", newline="\n")
    print("Wrote Dockerfile, docker-compose.yml, init.sql")


if __name__ == "__main__":
    main()
