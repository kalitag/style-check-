# ReviewCheckk Style Telegram Bot 🤖

A smart Telegram bot that automatically formats affiliate product posts in ReviewCheckk style. The bot intelligently extracts product information, cleans titles, resolves shortened URLs, and formats everything professionally.

## Features ✨

- **Smart URL Processing**: Automatically unshortens links from major shortening services
- **Intelligent Title Cleaning**: Extracts and cleans product titles from web pages
- **Price Detection**: Finds and formats prices from messages or product pages
- **Meesho Special Handling**: Automatically adds Size and PIN for Meesho products
- **Multi-Platform Support**: Works with Amazon, Flipkart, Meesho, and other e-commerce sites
- **Error Resilient**: Handles network failures and malformed data gracefully

## Bot Information 📱

- **Bot Token**: `8214627280:AAGveHdnt41wfXIaNunu6RBPsHDqMfIZo5E`
- **Username**: `@reviewcheck_style_bot`

## Output Format 📝

### Non-Meesho Products
```
Clean Product Title @999 rs
https://www.amazon.in/dp/B07S86BF9T
```

### Meesho Products
```
Women Cotton Printed Kurta @499 rs
https://www.meesho.com/product/abcd123
Size - All
Pin - 110001
```

## Installation & Setup 🚀

### Local Development

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/reviewcheck-telegram-bot.git
   cd reviewcheck-telegram-bot
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the bot**:
   ```bash
   python bot.py
   ```

### Deploy on Heroku

1. **Create Heroku app**:
   ```bash
   heroku create your-bot-name
   ```

2. **Set environment variables** (if needed):
   ```bash
   heroku config:set BOT_TOKEN=your_bot_token
   ```

3. **Deploy**:
   ```bash
   git push heroku main
   ```

### Deploy on Render

1. Connect your GitHub repository to Render
2. Create a new Web Service
3. Use the following settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`

## Usage 💡

1. **Add the bot** to your Telegram chat: `@reviewcheck_style_bot`

2. **Send messages** with product links:
   - Text messages with links
   - Photos with captions containing links
   - Forwarded messages with product links

3. **Bot processes automatically**:
   - Unshortens any shortened URLs
   - Extracts clean product title
   - Finds price information
   - Formats in ReviewCheckk style

## Supported Platforms 🛒

- **Amazon India** (amazon.in)
- **Flipkart** (flipkart.com)
- **Meesho** (meesho.com) - with special Size/PIN handling
- **Most e-commerce sites** with proper meta tags

## Supported URL Shorteners 🔗

- amzn.to, fkrt.cc, spoo.me, wishlink.com
- bitli.in, da.gd, cutt.ly, bit.ly
- tinyurl.com, goo.gl, t.co, and more

## Technical Features 🔧

### Smart Title Cleaning
- Removes marketing fluff ("best offer", "trending", etc.)
- Handles clothing items with gender/quantity formatting
- Validates titles to reject nonsense content
- Proper capitalization and word count limits

### Price Intelligence
- Prioritizes user-provided prices in messages
- Multiple price detection patterns
- Handles price ranges and currency formats
- Clean formatting without symbols

### URL Processing
- Follows redirects to get final URLs
- Removes tracking parameters (UTM, affiliate tags)
- Handles network timeouts gracefully
- Desktop user-agent for better scraping

### Meesho Enhancement
- Auto-detects Meesho links
- Extracts size information from messages
- Detects 6-digit PIN codes
- Uses default values when not found

## Error Handling 🛡️

- Network timeouts and connection errors
- Invalid or malformed URLs
- Missing product information
- Rate limiting and anti-bot measures
- Graceful fallbacks for all operations

## File Structure 📁

```
reviewcheck-telegram-bot/
├── bot.py              # Main bot application
├── requirements.txt    # Python dependencies
├── README.md          # This documentation
├── Procfile           # For Heroku deployment
├── .gitignore         # Git ignore rules
└── runtime.txt        # Python version specification
```

## Contributing 🤝

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License 📄

This project is licensed under the MIT License - see the LICENSE file for details.

## Support 💬

For issues and questions:
- Create an issue on GitHub
- Contact the bot directly on Telegram

## Changelog 📝

### v1.0.0
- Initial release
- Basic URL unshortening
- Title extraction and cleaning
- Price detection
- Meesho special handling
- Multi-platform support

---

**Made with ❤️ for affiliate marketers and deal sharers**