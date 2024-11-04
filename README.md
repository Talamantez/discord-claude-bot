# Discord Goals Bot 🎯

A Discord bot that helps teams track and manage SMART objectives using Claude AI.

## Features

- 🎯 Create SMART objectives with AI assistance
- 📊 List all objectives with pagination
- 💡 AI-powered formatting of goals into SMART criteria
- 📝 Automatic bullet point formatting
- 💾 Persistent storage with automatic backups

## Commands

- `!set_objective <text>` - Create a new SMART objective
  ```
  Example: !set_objective increase website traffic by 25%
  ```

- `!list` - Show all objectives (paginated)
  ```
  Shows 3 objectives per page with status and details
  ```

- `!test` - Check if bot is running
  ```
  Responds with "I'm working! 🎉"
  ```

## Setup

1. Clone the repository
```bash
git clone https://github.com/yourusername/discord-goals-bot.git
cd discord-goals-bot
```

2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Create `.env` file with your tokens:
```env
DISCORD_TOKEN=your_discord_bot_token
ANTHROPIC_API_KEY=your_claude_api_key
```

5. Run the bot
```bash
python src/goals_bot.py
```

## Development

### Project Structure
```
discord-goals-bot/
├── src/
│   ├── __init__.py
│   ├── goals_bot.py          # Main bot code
│   └── setup_commands.py     # Command definitions
├── tests/
│   ├── __init__.py
│   └── test_goals_bot.py     # Test suite
├── requirements.txt
├── pytest.ini
└── README.md
```

### Running Tests
```bash
# Run all tests
python -m pytest tests/

# Run tests with coverage
python -m pytest tests/ -v --cov=src
```

### Code Coverage
Current test coverage: 82%
- src/goals_bot.py: 82%
- src/setup_commands.py: 81%

## Technical Details

### Core Components

1. **GoalsDatabase**
   - JSON-based persistent storage
   - Automatic backup creation
   - Error handling for file operations

2. **CompanyAssistant**
   - Discord.py bot implementation
   - Claude AI integration
   - Command handling
   - Text formatting utilities

3. **Command Setup**
   - Modular command registration
   - Production/testing environment handling
   - Error handling and user feedback

### Dependencies

- discord.py: Discord API wrapper
- anthropic: Claude AI integration
- python-dotenv: Environment management
- pytest: Testing framework

## Environment Variables

| Variable | Description |
|----------|-------------|
| DISCORD_TOKEN | Your Discord bot token |
| ANTHROPIC_API_KEY | Your Anthropic/Claude API key |

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the test suite
5. Submit a pull request

## Testing

The test suite covers:
- Command functionality
- Database operations
- Text formatting
- Error handling
- Environment setup

Run tests with:
```bash
python -m pytest tests/ -v --cov=src
```

## Error Handling

The bot includes comprehensive error handling for:
- Invalid commands
- API failures
- Database errors
- File operations
- Message size limits

Error messages are formatted and sent back to Discord for user visibility.

## Best Practices

1. **SMART Goals**
   - Specific: Clear and unambiguous
   - Measurable: Quantifiable objectives
   - Achievable: Realistic goals
   - Relevant: Aligned with overall purpose
   - Time-bound: Clear deadlines

2. **Database Management**
   - Automatic backups
   - Atomic operations
   - Error recovery

3. **Discord Integration**
   - Proper message formatting
   - Pagination for large datasets
   - User-friendly error messages

## License

MIT License - feel free to use and modify as needed.