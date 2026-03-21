<?php
// Параметры, полученные от my.telegram.org
$api_id = 29432513; // Замените на свой api_id
$api_hash = 'c40b383978049f6816cf0b06c9c537c9'; // Замените на свой api_hash
$phone_number = '+79651351990'; // Ваш номер телефона, зарегистрированный в Telegram

// Убедимся, что MadelineProto загружена
if (!file_exists('madeline.php')) {
    copy('https://phar.madelineproto.xyz/madeline.php', 'madeline.php');
}
include_once 'madeline.php';

/**
 * Функция для безопасного чтения ввода из консоли (скрывает ввод пароля)
 */
function readlineSilent($prompt = "Enter Password: ") {
    echo $prompt;
    system('stty -echo');
    $password = trim(fgets(STDIN));
    system('stty echo');
    echo "\n";
    return $password;
}

/**
 * Основная логика
 */
try {
    // 1. Настройка параметров приложения
    $settings = (new \danog\MadelineProto\Settings\AppInfo)
        ->setApiId($api_id)
        ->setApiHash($api_hash);

    // 2. Создание экземпляра API с именем файла сессии
    //    Сессия будет сохранена в папке 'sessions/имя_сессии'
    $MadelineProto = new \danog\MadelineProto\API('sessions/' . md5($phone_number) . '.session', $settings);

    // 3. Запуск и проверка авторизации
    //    Библиотека сама управляет состоянием сессии.
    //    Мы используем start(), который либо сразу запустит бота/юзера,
    //    либо выбросит исключение, требуя авторизации.
    echo "Попытка авторизации...\n";
    $MadelineProto->start();

    // В текущих версиях MadelineProto нет isAuthorized(), проверяем статус через getAuthorization().
    if ($MadelineProto->getAuthorization() !== \danog\MadelineProto\API::LOGGED_IN) {
        echo "Не авторизован.\n";
        return;
        // Отправляем запрос на код
        // $sentCode = $MadelineProto->phoneLogin($phone_number);
        // echo "Код отправлен на $phone_number\n";

        // // Запрашиваем код
        // readline('Введите код из Telegram: ');
        // $verification_code = readline('');
        // $authorization = $MadelineProto->completePhoneLogin($verification_code);

        // // Проверяем, нужен ли облачный пароль (2FA)
        // if (isset($authorization['_']) && $authorization['_'] === 'account.password') {
        //     echo "Требуется облачный пароль.\n";
        //     $password_2fa = readlineSilent('Введите ваш облачный пароль: ');
        //     $authorizatioln = $MadelineProto->complete2faLogin($password_2fa);
        // }

        // echo "Авторизация успешна!\n";
    } else {
        echo "Уже авторизован. Использую существующую сессию.\n";
        // Если уже авторизован, просто запускаем сессию
        $MadelineProto->start();
    }
    // 4. ПАРСИНГ СООБЩЕНИЙ ИЗ КАНАЛА
    //    Указываем имя канала (можно без @)
    $invite_link = '@warhammerstlfree'; // или t.me/durov
    // $chat_info = $MadelineProto->getInfo($invite_link);

    // $supergroup_id = '-1002135409517';//$chat_info['channel_id']; // ID супергруппы-форума
    // $topic_id = '60'; // ID темы, которую нужно спарсить

    // // Создаем InputPeer для темы
    // $inputPeer = [
    //     '_' => 'inputPeerChannelFromMessage', // Специальный тип для тем
    //     'peer' => $supergroup_id,             // ID супергруппы
    //     'msg_id' => $topic_id,                // ID темы (сообщения-начала темы)
    //     // Внимание: 'msg_id' - это ID первого сообщения в теме,
    //     // а не числовой ID темы, который виден в URL. Его нужно получать отдельно.
    // ];

    // $topic_info = $MadelineProto->getInfo($inputPeer);
    // $inputPeer = $topic_info['InputPeer']; // Готовый InputPeer для этой темы
    
    //$channel_username = $inputPeer['InputPeer'];
    $channel_username = $invite_link;

    echo "\n--- Парсинг канала @$channel_username ---\n";

    // Получаем историю сообщений
    // Используем метод messages.getHistory
    $messages = $MadelineProto->messages->getHistory([
        'peer' => $channel_username,   // Кого парсим
        'offset_id' => 0,               // Начинаем с самого нового
        'offset_date' => 0,
        'add_offset' => 0,
        'limit' => 10,                   // Количество последних сообщений
        'max_id' => 0,                    // ID последнего сообщения (0 - без ограничений)
        'min_id' => 0,                     // ID первого сообщения (0 - без ограничений)
        'hash' => 0,
    ]);

    // Массив сообщений находится в $messages['messages']
    if (isset($messages['messages']) && count($messages['messages']) > 0) {
        // Сообщения приходят в порядке от нового к старому, разворачиваем для удобства
        foreach (array_reverse($messages['messages']) as $message) {
            // '_' содержит тип сообщения, например 'message'
            $message_text = $message['message'] ?? 'Нет текста (возможно, медиа)';
            $message_date = date('Y-m-d H:i:s', $message['date']);
            $message_views = $message['views'] ?? 0;

            echo "-----------------------------\n";
            echo "Дата: $message_date\n";
            echo "Просмотры: $message_views\n";
            echo "Текст: $message_text\n";
        }
    } else {
        echo "Не удалось получить сообщения или канал пуст.\n";
    }

    echo "-----------------------------\n";
    echo "Готово.\n";

} catch (\danog\MadelineProto\Exception $e) {
    echo "Ошибка MadelineProto: " . $e->getMessage() . "\n";
} catch (\Throwable $e) {
    echo "Общая ошибка: " . $e->getMessage() . "\n";
}
