<?php

namespace App\Command\ImportTelegram;

use App\Service\CouchDB;
use App\Service\MadelineTelegram;
use Symfony\Component\Console\Attribute\AsCommand;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputArgument;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Input\InputOption;
use Symfony\Component\Console\Output\OutputInterface;
use Symfony\Component\Console\Style\SymfonyStyle;

use danog\MadelineProto\API;
use danog\MadelineProto\Logger;
use danog\MadelineProto\SettingsAbstract;

use GuzzleHttp\Client as CouchDBClient;

#[AsCommand(
    name: 'app:import-telegram',
    description: 'Add a short description for your command',
)]
class ImportTelegramCommand extends Command
{
    public function __construct(MadelineTelegram $madelineTelegram, CouchDB $couchDB)
    {
        parent::__construct();

        $this->couchdb = $couchDB->initCouchDB();
        $this->dbName = $couchDB->dbName;
        // Initialize MadelineProto
        $this->madeline = $madelineTelegram->initMadelineProto();
    }

    protected function configure(): void
    {
        $this
            ->addArgument('arg1', InputArgument::OPTIONAL, 'Argument description')
            ->addOption('option1', null, InputOption::VALUE_NONE, 'Option description')
        ;
    }

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        $io = new SymfonyStyle($input, $output);
        $arg1 = $input->getArgument('arg1');

        if ($arg1) {
            $io->note(sprintf('You passed an argument: %s', $arg1));
        }

        if ($input->getOption('option1')) {
            // ...
        }

        $groupId = \App\Const\Connection::GROUP_ID;

        $this->mapGroupMessages($groupId);

        $io->success('You have a new command! Now make it your own! Pass --help to see your options.');

        return Command::SUCCESS;
    }
    private $madeline;
    private $couchdb;
    private $dbName;
    
    
    
    public function mapGroupMessages($groupId) {
        // Get information about the group
        $groupInfo = $this->madeline->getPwrChat($groupId);
        
        echo "Processing group: {$groupInfo['title']}\n";
        // var_dump($groupInfo);
        
        $totalMessages = 0;
        $lastMessageId = 0;
        
        do {
            $messages = $this->madeline->messages->getHistory(
                peer: $groupId,
                offset_id: $lastMessageId,
                offset_date: 0,
                add_offset: 0,
                limit: 100, // Number of messages to retrieve per request
                max_id: 0,
                min_id: 0,
            );
            
            if (empty($messages['messages'])) {
                break;
            }
            
            foreach ($messages['messages'] as $message) {
                if (isset($message['id'])) {
                    $lastMessageId = $message['id'];
                    
                    // Prepare document for CouchDB
                    $doc = [
                        '_id' => "tg_{$groupId}_{$message['id']}",
                        'source' => 'telegram',
                        'group_id' => $groupId,
                        'group_name' => $groupInfo['title'],
                        'message_id' => $message['id'],
                        'date' => date('Y-m-d H:i:s', $message['date']),
                        'timestamp' => $message['date'],
                        'content' => $this->extractMessageContent($message),
                        'sender' => $this->extractSenderInfo($message),
                        'raw' => $message // Store the complete raw message
                    ];
                    
                    // Save to CouchDB
                    $this->saveToCouchDB($doc);
                    
                    $totalMessages++;
                    if ($totalMessages % 100 === 0) {
                        echo "Processed {$totalMessages} messages...\n";
                    }
                }
            }
            
        } while (count($messages['messages']) > 0);
        
        echo "Completed! Total messages processed: {$totalMessages}\n";
    }
    
    private function extractMessageContent($message) {
        if (isset($message['message'])) {
            return $message['message'];
        } elseif (isset($message['media'])) {
            $mediaType = $message['media']['_'];
            return "[MEDIA: {$mediaType}]";
        }
        return '';
    }
    
    private function extractSenderInfo($message) {
        if (!isset($message['from_id'])) {
            return null;
        }
        
        try {
            $user = $this->madeline->getPwrChat($message['from_id']);
            return [
                'id' => $user['id'],
                'name' => $user['first_name'] . (isset($user['last_name']) ? ' ' . $user['last_name'] : ''),
                'username' => $user['username'] ?? null
            ];
        } catch (\Exception $e) {
            return [
                'id' => $message['from_id'],
                'name' => 'Unknown',
                'username' => null
            ];
        }
    }
    
    private function saveToCouchDB($doc) {
        try {
            $response = $this->couchdb->put("{$this->dbName}/{$doc['_id']}", [
                'json' => $doc
            ]);
            
            if ($response->getStatusCode() !== 201) {
                echo "Failed to save document {$doc['_id']}\n";
            }
        } catch (\Exception $e) {
            // Document might already exist, try to update
            try {
                // Get current revision
                $response = $this->couchdb->get("{$this->dbName}/{$doc['_id']}");
                $existing = json_decode($response->getBody(), true);
                
                // Update with new revision
                $doc['_rev'] = $existing['_rev'];
                $this->couchdb->put("{$this->dbName}/{$doc['_id']}", [
                    'json' => $doc
                ]);
            } catch (\Exception $e) {
                echo "Error saving document {$doc['_id']}: " . $e->getMessage() . "\n";
            }
        }
    }
}
