FROM ubuntu:noble

RUN apt-get -y update && apt-get install -y php8.3 wget git php8.3-curl php8.3-xml php8.3-zip php8.3-pdo php8.3-mysql php8.3-mbstring php8.3-xdebug unzip f3d

RUN wget https://get.symfony.com/cli/installer -O - | bash
RUN mv /root/.symfony5/bin/symfony /usr/local/bin/symfony

RUN php -r "copy('https://getcomposer.org/installer', 'composer-setup.php');"
RUN php composer-setup.php
RUN php -r "unlink('composer-setup.php');"
RUN mv composer.phar /usr/local/bin/composer

COPY ./.infrastructure/php/20-xdebug.ini /etc/php/8.3/cli/conf.d/20-xdebug.ini

RUN mkdir /app
RUN chown -R www-data:www-data /app

COPY ./.infrastructure/apache2/sites-enabled/000-default.conf /etc/apache2/sites-enabled/000-default.conf

# RUN sed -i 's/<regex>/<replacement>/g' <input file

RUN a2enmod rewrite
RUN service apache2 restart

CMD ["/usr/sbin/apachectl", "-D", "FOREGROUND"]