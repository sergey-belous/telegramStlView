<?php

namespace App\Service;

use danog\MadelineProto\API;
use danog\MadelineProto\Logger;
use danog\MadelineProto\Settings;

class MadelineTelegram
{
    public ?API $madeline = null;

    public function __construct(
        public string $rootDir
    ){}

    public function initMadelineProto(): ?API {
        if (!$this->madeline) {
            $settings = [
                'logger' => [
                    'logger_level' => Logger::ULTRA_VERBOSE,
                    'logger' => Logger::ECHO_LOGGER,
                ],
                'app_info' => [
                    'api_id' => 29432513,      // Replace with your API ID
                    'api_hash' => 'c40b383978049f6816cf0b06c9c537c9',   // Replace with your API hash
                ],
            ];

            // $c_setting = new Settings();
            $this->madeline = new API($this->rootDir . 'session.madeline');
            $this->madeline->start();
        }
        return $this->madeline;
    }
}