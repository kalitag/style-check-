import asyncio
import re
import logging
from urllib.parse import urlparse, parse_qs, urlunparse
from typing import Optional, List, Dict, Tuple
import requests
from bs4 import BeautifulSoup
from telegram import Update, Message
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class URLResolver:
    """Handle URL unshortening and cleaning"""
    
    SHORTENERS = [
        'amzn.to', 'fkrt.cc', 'spoo.me', 'wishlink.com', 'bitli.in', 
        'da.gd', 'cutt.ly', 'bit.ly', 'tinyurl.com', 'goo.gl', 't.co',
        'short.me', 'u.to', 'ow.ly', 'tiny.cc', 'is.gd'
    ]
    
    TRACKING_PARAMS = [
        'tag', 'ref', 'refRID', 'pf_rd_r', 'pf_rd_p', 'pf_rd_m', 
        'pf_rd_t', 'pf_rd_s', 'pf_rd_i', 'utm_source', 'utm_medium', 
        'utm_campaign', 'utm_term', 'utm_content', 'gclid', 'fbclid',
        'mc_cid', 'mc_eid', '_gl', 'igshid', 'si'
    ]
    
    @staticmethod
    def detect_links(text: str) -> List[str]:
        """Extract all URLs from text"""
        url_pattern = r'https?://(?:[-\w.])+(?::[0-9]+)?(?:/(?:[\w/_.])*)?(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?'
        return re.findall(url_pattern, text)
    
    @staticmethod
    def is_shortener(url: str) -> bool:
        """Check if URL is from a shortening service"""
        domain = urlparse(url).netloc.lower()
        return any(shortener in domain for shortener in URLResolver.SHORTENERS)
    
    @staticmethod
    async def unshorten_url(url: str) -> str:
        """Resolve shortened URL to final destination"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            def make_request():
                response = requests.get(url, headers=headers, allow_redirects=True, timeout=2.5)
                return response.url
            
            final_url = await asyncio.to_thread(make_request)
            return URLResolver.clean_url(final_url)
            
        except Exception as e:
            logger.warning(f"Failed to unshorten URL {url}: {e}")
            return URLResolver.clean_url(url)
    
    @staticmethod
    def clean_url(url: str) -> str:
        """Remove tracking parameters from URL"""
        try:
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            
            # Remove tracking parameters
            cleaned_params = {
                k: v for k, v in query_params.items() 
                if k not in URLResolver.TRACKING_PARAMS
            }
            
            # Rebuild query string
            if cleaned_params:
                query_string = '&'.join(f"{k}={v[0]}" for k, v in cleaned_params.items())
                cleaned = parsed._replace(query=query_string)
            else:
                cleaned = parsed._replace(query='')
            
            return urlunparse(cleaned)
            
        except Exception:
            return url

class TitleCleaner:
    """Extract and clean product titles"""
    
    FLUFF_WORDS = [
        'best offer', 'trending', 'stylish', 'buy online', 'india', 'amazon.in',
        'flipkart', 'official store', 'exclusive', 'limited time', 'deal',
        'sale', 'discount', 'offer', 'free shipping', 'cod available',
        'cash on delivery', 'lowest price', 'great indian', 'festival'
    ]
    
    CLOTHING_KEYWORDS = [
        'kurta', 'shirt', 'dress', 'top', 'bottom', 'jeans', 'trouser',
        'saree', 'lehenga', 'suit', 'kurti', 'palazzo', 'dupatta',
        'blouse', 'skirt', 'shorts', 'tshirt', 't-shirt'
    ]
    
    @staticmethod
    async def extract_title_from_url(url: str) -> Optional[str]:
        """Extract title from product page"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            def scrape_title():
                response = requests.get(url, headers=headers, timeout=3)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Try og:title first
                og_title = soup.find('meta', property='og:title')
                if og_title and og_title.get('content'):
                    return og_title['content'].strip()
                
                # Try page title
                title_tag = soup.find('title')
                if title_tag and title_tag.text:
                    return title_tag.text.strip()
                
                # Try h1
                h1_tag = soup.find('h1')
                if h1_tag and h1_tag.text:
                    return h1_tag.text.strip()
                
                return None
            
            return await asyncio.to_thread(scrape_title)
            
        except Exception as e:
            logger.warning(f"Failed to extract title from {url}: {e}")
            return None
    
    @staticmethod
    def clean_title(raw_title: str) -> str:
        """Clean and format product title"""
        if not raw_title:
            return ""
        
        # Remove emojis and special characters
        title = re.sub(r'[^\w\s\-&()]', ' ', raw_title)
        
        # Remove fluff words
        for fluff in TitleCleaner.FLUFF_WORDS:
            title = re.sub(re.escape(fluff), '', title, flags=re.IGNORECASE)
        
        # Normalize whitespace
        title = ' '.join(title.split())
        
        # Reject nonsense titles
        if TitleCleaner.is_nonsense_title(title):
            return ""
        
        # Format based on product type
        if TitleCleaner.is_clothing_item(title):
            return TitleCleaner.format_clothing_title(title)
        else:
            return TitleCleaner.format_general_title(title)
    
    @staticmethod
    def is_nonsense_title(title: str) -> bool:
        """Check if title is nonsense/invalid"""
        if len(title) < 3:
            return True
        
        # Check for lack of vowels
        vowel_count = len([c for c in title.lower() if c in 'aeiou'])
        if vowel_count < len(title) * 0.1:  # Less than 10% vowels
            return True
        
        # Check for repeated characters
        if re.search(r'(.)\1{4,}', title):  # Same char repeated 5+ times
            return True
        
        return False
    
    @staticmethod
    def is_clothing_item(title: str) -> bool:
        """Check if product is clothing item"""
        return any(keyword in title.lower() for keyword in TitleCleaner.CLOTHING_KEYWORDS)
    
    @staticmethod
    def format_clothing_title(title: str) -> str:
        """Format clothing title: [Brand] [Gender] [Quantity] [Product]"""
        words = title.split()[:8]  # Max 8 words
        
        # Extract brand (usually first word)
        brand = words[0] if words else ""
        
        # Detect gender
        gender = ""
        if any(word.lower() in ['women', 'womens', 'ladies', 'girls'] for word in words):
            gender = "Women"
        elif any(word.lower() in ['men', 'mens', 'boys', 'male'] for word in words):
            gender = "Men"
        
        # Extract product type
        product_words = [word for word in words[1:] if word.lower() not in ['women', 'womens', 'men', 'mens', 'ladies', 'boys', 'girls']]
        product = ' '.join(product_words[:4])  # Max 4 words for product
        
        # Build final title
        parts = [brand]
        if gender:
            parts.append(gender)
        if product:
            parts.append(product)
        
        return ' '.join(parts).title()
    
    @staticmethod
    def format_general_title(title: str) -> str:
        """Format general title: [Brand] [Product]"""
        words = title.split()[:6]  # Max 6 words
        return ' '.join(words).title()

class PriceExtractor:
    """Extract and format prices"""
    
    @staticmethod
    def extract_price(text: str) -> Optional[str]:
        """Extract price from text"""
        # Look for price patterns
        price_patterns = [
            r'(?:₹|Rs?\.?\s*)(\d[\d,]*)',  # ₹1299 or Rs. 1299
            r'(\d[\d,]*)\s*(?:₹|Rs?\.?)',  # 1299₹ or 1299 Rs
            r'price\s*:?\s*(?:₹|Rs?\.?\s*)(\d[\d,]*)',  # price: ₹1299
            r'cost\s*:?\s*(?:₹|Rs?\.?\s*)(\d[\d,]*)',   # cost: ₹1299
            r'@\s*(\d[\d,]*)\s*rs',  # @1299 rs
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                price = matches[0].replace(',', '')
                if price.isdigit() and int(price) > 0:
                    return price
        
        return None
    
    @staticmethod
    def format_price(price: str) -> str:
        """Format price in ReviewCheckk style"""
        if not price:
            return "@rs"
        return f"@{price} rs"

class PinDetector:
    """Detect PIN codes from messages"""
    
    @staticmethod
    def extract_pin(text: str) -> str:
        """Extract 6-digit PIN code from text"""
        pin_pattern = r'\b(\d{6})\b'
        matches = re.findall(pin_pattern, text)
        
        for pin in matches:
            # Validate PIN (should not be all same digits or sequential)
            if len(set(pin)) > 1 and not re.match(r'123456|654321', pin):
                return pin
        
        return "110001"  # Default PIN for Delhi

class ResponseBuilder:
    """Build formatted responses"""
    
    @staticmethod
    def build_response(title: str, url: str, price: str, is_meesho: bool = False, 
                      size: str = "All", pin: str = "110001") -> str:
        """Build final formatted response"""
        
        if not title:
            return "❌ Unable to extract product info"
        
        # Format price
        formatted_price = PriceExtractor.format_price(price)
        
        # Build base response
        response = f"{title} {formatted_price}\n{url}"
        
        # Add Meesho-specific info
        if is_meesho:
            response += f"\nSize - {size}\nPin - {pin}"
        
        return response

class ReviewCheckkBot:
    """Main bot class"""
    
    def __init__(self, token: str):
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup message handlers"""
        # Handle all messages with links or images
        self.application.add_handler(
            MessageHandler(
                filters.TEXT | filters.PHOTO | filters.FORWARDED,
                self.handle_message
            )
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main message handler"""
        try:
            message = update.message
            
            # Get text from message or caption
            text = self.extract_text(message)
            
            if not text:
                if message.photo:
                    await message.reply_text("No title provided")
                return
            
            # Extract and process URLs
            urls = URLResolver.detect_links(text)
            
            if not urls:
                return  # No URLs to process
            
            # Process each URL
            for url in urls:
                response = await self.process_url(url, text)
                if response:
                    await message.reply_text(response, parse_mode=None)
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await update.message.reply_text("❌ Unable to extract product info")
    
    def extract_text(self, message: Message) -> str:
        """Extract text from message or caption"""
        if message.text:
            return message.text
        elif message.caption:
            return message.caption
        elif message.forward_from and hasattr(message.forward_from, 'text'):
            return message.forward_from.text
        return ""
    
    async def process_url(self, url: str, message_text: str) -> Optional[str]:
        """Process a single URL and return formatted response"""
        try:
            # Unshorten URL if needed
            if URLResolver.is_shortener(url):
                final_url = await URLResolver.unshorten_url(url)
            else:
                final_url = URLResolver.clean_url(url)
            
            # Extract title from URL
            scraped_title = await TitleCleaner.extract_title_from_url(final_url)
            
            # Use scraped title or fallback to message text
            if scraped_title:
                clean_title = TitleCleaner.clean_title(scraped_title)
            else:
                # Try to extract title from message text
                clean_title = TitleCleaner.clean_title(message_text)
            
            # Extract price (prioritize message text)
            price = PriceExtractor.extract_price(message_text)
            if not price:
                # Try to extract from URL (future enhancement)
                price = None
            
            # Check if it's Meesho
            is_meesho = 'meesho.com' in final_url.lower()
            
            # For Meesho, extract size and pin
            size = "All"
            pin = "110001"
            
            if is_meesho:
                # Extract size from message
                size_match = re.search(r'size\s*:?\s*([^\n,]+)', message_text, re.IGNORECASE)
                if size_match:
                    size = size_match.group(1).strip()
                
                # Extract PIN
                pin = PinDetector.extract_pin(message_text)
            
            # Build and return response
            return ResponseBuilder.build_response(
                clean_title, final_url, price, is_meesho, size, pin
            )
            
        except Exception as e:
            logger.error(f"Error processing URL {url}: {e}")
            return "❌ Unable to extract product info"
    
    def run(self):
        """Start the bot"""
        logger.info("Starting ReviewCheckk Style Bot...")
        self.application.run_polling()

def main():
    """Main function"""
    # Bot token
    TOKEN = "8214627280:AAGveHdnt41wfXIaNunu6RBPsHDqMfIZo5E"
    
    # Create and run bot
    bot = ReviewCheckkBot(TOKEN)
    bot.run()

if __name__ == "__main__":
    main()