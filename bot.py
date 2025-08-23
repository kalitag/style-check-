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
        'cash on delivery', 'lowest price', 'great indian', 'festival',
        'for parties', 'cool', 'attractive', 'beautiful', 'amazing',
        'super', 'premium', 'high quality', 'branded', 'original'
    ]
    
    CLOTHING_KEYWORDS = [
        'kurta', 'shirt', 'dress', 'top', 'bottom', 'jeans', 'trouser',
        'saree', 'lehenga', 'suit', 'kurti', 'palazzo', 'dupatta',
        'blouse', 'skirt', 'shorts', 'tshirt', 't-shirt', 'hoodie',
        'jacket', 'coat', 'sweater', 'cardigan', 'blazer'
    ]
    
    GENDER_KEYWORDS = {
        'women': ['women', 'womens', 'ladies', 'girls', 'female', 'girl'],
        'men': ['men', 'mens', 'boys', 'male', 'boy', 'gents'],
        'kids': ['kids', 'child', 'children', 'baby', 'infant'],
        'unisex': ['unisex', 'couple']
    }
    
    QUANTITY_PATTERNS = [
        r'pack of (\d+)', r'set of (\d+)', r'(\d+)\s*pcs?', r'(\d+)\s*pieces?',
        r'(\d+)\s*units?', r'(\d+)\s*kg', r'(\d+)\s*g\b', r'(\d+)\s*ml',
        r'(\d+)\s*l\b', r'combo of (\d+)', r'(\d+)\s*pairs?',
        r'multipack\s*(\d+)', r'(\d+)\s*in\s*1'
    ]
    
    @staticmethod
    async def extract_title_from_url(url: str) -> Optional[str]:
        """Extract title from product page with improved headers and fallback logic"""
        try:
            # Rotate user agents and add more headers to avoid blocking
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
                'Mozilla/5.0 (Android 13; Mobile; rv:109.0) Gecko/113.0 Firefox/113.0'
            ]
            
            import random
            headers = {
                'User-Agent': random.choice(user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9,hi;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0',
                'Referer': 'https://www.google.com/'
            }
            
            def scrape_title():
                session = requests.Session()
                session.headers.update(headers)
                
                # Add delay to avoid rate limiting
                import time
                time.sleep(0.8)
                
                response = session.get(url, timeout=8, allow_redirects=True, verify=False)
                
                # Don't raise for status - handle different response codes
                if response.status_code not in [200, 201, 202]:
                    logger.warning(f"Non-200 status code {response.status_code} for {url}")
                    return None
                
                soup = BeautifulSoup(response.content, 'html.parser')
                domain = urlparse(url).netloc.lower()
                
                title_candidates = []
                
                # Domain-specific extraction first (most reliable)
                if 'meesho.com' in domain:
                    selectors = [
                        'span[data-testid="product-title"]',
                        'h1[data-testid="product-title"]',
                        '.Text__StyledText-sc-oo0kvp-0',
                        'span.Text__StyledText-sc-oo0kvp-0'
                    ]
                    for selector in selectors:
                        element = soup.select_one(selector)
                        if element and element.get_text(strip=True):
                            title_candidates.append(element.get_text(strip=True))
                
                elif 'flipkart.com' in domain:
                    selectors = [
                        'span.B_NuCI',
                        'h1.x2cTzZ',
                        'span._35KyD6',
                        '.B_NuCI'
                    ]
                    for selector in selectors:
                        element = soup.select_one(selector)
                        if element and element.get_text(strip=True):
                            title_candidates.append(element.get_text(strip=True))
                
                elif 'amazon' in domain:
                    selectors = [
                        '#productTitle',
                        'span#productTitle',
                        '.product-title'
                    ]
                    for selector in selectors:
                        element = soup.select_one(selector)
                        if element and element.get_text(strip=True):
                            title_candidates.append(element.get_text(strip=True))
                
                elif 'wishlink.com' in domain or 'extp.in' in domain or 'faym.co' in domain:
                    # These are affiliate link redirectors - try generic selectors
                    selectors = [
                        'h1', '.product-title', '.title', '#title',
                        '.product-name', '.item-title'
                    ]
                    for selector in selectors:
                        element = soup.select_one(selector)
                        if element and element.get_text(strip=True):
                            title_candidates.append(element.get_text(strip=True))
                
                # Generic meta tag extraction
                meta_selectors = [
                    'meta[property="og:title"]',
                    'meta[name="twitter:title"]',
                    'meta[name="title"]',
                    'meta[property="product:name"]'
                ]
                
                for selector in meta_selectors:
                    meta = soup.select_one(selector)
                    if meta and meta.get('content'):
                        title_candidates.append(meta['content'].strip())
                
                # Page title as fallback
                title_tag = soup.find('title')
                if title_tag and title_tag.get_text(strip=True):
                    title_candidates.append(title_tag.get_text(strip=True))
                
                # H1 tags as fallback
                h1_tags = soup.find_all('h1')
                for h1 in h1_tags[:3]:  # Check first 3 h1 tags
                    if h1 and h1.get_text(strip=True):
                        title_candidates.append(h1.get_text(strip=True))
                
                # Filter and return best candidate
                valid_titles = []
                for title in title_candidates:
                    if (title and len(title.strip()) > 10 and 
                        not TitleCleaner.is_nonsense_title(title) and
                        len(title.strip()) < 200):  # Not too long
                        valid_titles.append(title.strip())
                
                if valid_titles:
                    # Return shortest meaningful title (usually most specific)
                    return min(valid_titles, key=len)
                
                return None
            
            return await asyncio.to_thread(scrape_title)
            
        except Exception as e:
            logger.warning(f"Failed to extract title from {url}: {e}")
            return None
    
    @staticmethod
    def clean_title(raw_title: str) -> str:
        """Clean and format product title according to new rules"""
        if not raw_title:
            return ""
        
        # Remove emojis and special characters except basic punctuation
        title = re.sub(r'[^\w\s\-&().]', ' ', raw_title)
        
        # Remove fluff words
        for fluff in TitleCleaner.FLUFF_WORDS:
            title = re.sub(re.escape(fluff), '', title, flags=re.IGNORECASE)
        
        # Normalize whitespace
        title = ' '.join(title.split())
        
        # Reject nonsense titles
        if TitleCleaner.is_nonsense_title(title):
            return ""
        
        # Extract components using new rules
        return TitleCleaner.format_with_new_rules(title)
    
    @staticmethod
    def format_with_new_rules(title: str) -> str:
        """Format title according to: [Gender] [Quantity] [Brand] [Product]"""
        if not title:
            return ""
            
        words = title.lower().split()
        
        # Filter out common noise words early
        noise_words = {'http', 'https', 'www', 'com', 'in', 'the', 'and', 'or', 'at', 'to', 'for'}
        words = [word for word in words if word not in noise_words and len(word) > 1]
        
        if not words:
            return ""
        
        # Extract components
        gender = TitleCleaner.extract_gender(words)
        quantity = TitleCleaner.extract_quantity(' '.join(words))
        brand = TitleCleaner.extract_brand(words)
        product = TitleCleaner.extract_product(words)
        
        # Build final title
        parts = []
        if gender:
            parts.append(gender)
        if quantity:
            parts.append(quantity)
        if brand:
            parts.append(brand)
        if product:
            # Split product and take max 3 words
            product_words = product.split()[:3]
            parts.extend(product_words)
        
        # Ensure we have at least some content
        if not parts:
            # Fallback: take first few meaningful words
            meaningful_words = [word.title() for word in words[:4] if len(word) > 2]
            parts = meaningful_words
        
        # Ensure max 8 words total
        final_parts = parts[:8]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_parts = []
        for part in final_parts:
            part_lower = part.lower()
            if part_lower not in seen and part_lower not in noise_words:
                seen.add(part_lower)
                unique_parts.append(part.title())
        
        result = ' '.join(unique_parts)
        
        # Final validation - ensure we have a meaningful result
        if len(result.strip()) < 3:
            # Emergency fallback - use first few original words
            fallback_words = [word.title() for word in words[:4]]
            result = ' '.join(fallback_words)
        
        return result.strip()
    
    @staticmethod
    def extract_gender(words: List[str]) -> Optional[str]:
        """Extract gender from words"""
        for gender, keywords in TitleCleaner.GENDER_KEYWORDS.items():
            if any(keyword in words for keyword in keywords):
                return gender.title()
        return None
    
    @staticmethod
    def extract_quantity(text: str) -> Optional[str]:
        """Extract quantity information"""
        for pattern in TitleCleaner.QUANTITY_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                quantity = match.group(1) if match.groups() else match.group(0)
                
                # Format based on pattern type
                if 'pack of' in pattern:
                    return f"Pack of {quantity}"
                elif 'set of' in pattern:
                    return f"Set of {quantity}"
                elif 'pcs' in pattern or 'pieces' in pattern:
                    return f"{quantity} Pcs"
                elif 'kg' in pattern:
                    return f"{quantity}kg"
                elif 'g' in pattern and 'kg' not in pattern:
                    return f"{quantity}g"
                elif 'ml' in pattern:
                    return f"{quantity}ml"
                elif 'l' in pattern and 'ml' not in pattern:
                    return f"{quantity}L"
                elif 'combo' in pattern:
                    return f"Combo of {quantity}"
                elif 'pairs' in pattern:
                    return f"{quantity} Pairs"
                elif 'multipack' in pattern:
                    return f"Multipack {quantity}"
                else:
                    return f"{quantity} Pcs"
        
        return None
    
    @staticmethod
    def extract_brand(words: List[str]) -> Optional[str]:
        """Extract brand name (usually first meaningful word)"""
        # Common brands to prioritize
        known_brands = [
            'nike', 'adidas', 'puma', 'reebok', 'boat', 'jbl', 'sony', 
            'samsung', 'apple', 'mi', 'realme', 'oneplus', 'vivo', 'oppo',
            'libas', 'aurelia', 'w', 'biba', 'global desi', 'chemistry'
        ]
        
        # Look for known brands first
        for word in words:
            if word in known_brands:
                return word.title()
        
        # If no known brand, take first meaningful word (not gender/quantity)
        for word in words:
            if (word not in [kw for kw_list in TitleCleaner.GENDER_KEYWORDS.values() for kw in kw_list] 
                and not re.match(r'\d+', word) 
                and len(word) > 2):
                return word.title()
        
        return None
    
    @staticmethod
    def extract_product(words: List[str]) -> str:
        """Extract product name (clothing items or main product)"""
        # Find clothing keywords first
        for word in words:
            if word in TitleCleaner.CLOTHING_KEYWORDS:
                return word.title()
        
        # If not clothing, extract meaningful product words
        product_words = []
        skip_words = {
            'for', 'with', 'and', 'or', 'the', 'a', 'an', 'in', 'on', 'at',
            'buy', 'get', 'best', 'new', 'old', 'good', 'great', 'super',
            'http', 'https', 'www', 'com', 'html', 'php', 'share'
        }
        
        # Skip gender and quantity words too
        gender_words = {kw for kw_list in TitleCleaner.GENDER_KEYWORDS.values() for kw in kw_list}
        all_skip_words = skip_words.union(gender_words)
        
        for word in words:
   for word in words:
    if (
        len(word) > 2
        and word not in all_skip_words
        and not re.match(r'^\d+$', word)  # skip pure numbers
        and not word.startswith('http')   # skip URLs
    ):
        product_words.append(word)

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
            
            # Extract title with multiple fallback strategies
            clean_title = None
            
            # Strategy 1: Check for forwarded title patterns in message
            forwarded_title = self.extract_forwarded_title(message_text)
            if forwarded_title:
                clean_title = TitleCleaner.clean_title(forwarded_title)
            
            # Strategy 2: Try scraping from final URL if no forwarded title
            if not clean_title:
                scraped_title = await TitleCleaner.extract_title_from_url(final_url)
                if scraped_title:
                    clean_title = TitleCleaner.clean_title(scraped_title)
            
            # Strategy 3: Extract from URL slug if scraping fails
            if not clean_title:
                url_title = self.extract_title_from_url_slug(final_url)
                if url_title:
                    clean_title = TitleCleaner.clean_title(url_title)
            
            # Strategy 4: Use message text as last resort
            if not clean_title:
                # Remove URL from message text first
                message_without_urls = re.sub(r'https?://\S+', '', message_text).strip()
                if message_without_urls:
                    clean_title = TitleCleaner.clean_title(message_without_urls)
            
            # If still no title, return error
            if not clean_title:
                return "❌ Unable to extract product info"
            
            # Extract price (prioritize message text)
            price = PriceExtractor.extract_price(message_text)
            
            # Check if it's Meesho
            is_meesho = 'meesho.com' in final_url.lower()
            
            # For Meesho, extract size and pin
            size = "All"
            pin = "110001"
            
            if is_meesho:
                # Extract size from message
                size_match = re.search(r'size\s*[-:]?\s*([^\n,]+)', message_text, re.IGNORECASE)
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
    
    def extract_forwarded_title(self, text: str) -> Optional[str]:
        """Extract title from forwarded message text patterns"""
        # Look for patterns like "Product Name @price rs"
        title_price_pattern = r'^([^@]+?)\s*@\d+\s*rs'
        match = re.search(title_price_pattern, text.strip(), re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Look for title on separate line before URL
        lines = text.strip().split('\n')
        for i, line in enumerate(lines):
            if 'http' in line and i > 0:  # URL found, check previous line
                potential_title = lines[i-1].strip()
                # Ensure it's not just domain or empty
                if (potential_title and len(potential_title) > 5 and 
                    not re.search(r'@\d+\s*rs', potential_title) and
                    not potential_title.lower().startswith('http')):
                    return potential_title
        
        return None
    
    def extract_title_from_url_slug(self, url: str) -> Optional[str]:
        """Extract product name from URL slug as fallback"""
        try:
            parsed_url = urlparse(url)
            path = parsed_url.path
            
            # Remove common path prefixes
            path = re.sub(r'^/(?:product|p|dp|item|share)', '', path)
            
            # Extract meaningful parts from path
            path_parts = [part for part in path.split('/') if part and len(part) > 2]
            
            if path_parts:
                # Take the longest part (usually product name)
                product_slug = max(path_parts, key=len)
                
                # Clean up the slug
                product_name = re.sub(r'[-_]', ' ', product_slug)
                product_name = re.sub(r'[^a-zA-Z0-9\s]', ' ', product_name)
                product_name = ' '.join(product_name.split())
                
                # Only return if it looks like a meaningful product name
                if len(product_name) > 5 and not product_name.isdigit():
                    return product_name
            
            return None
            
        except Exception:
            return None
    
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
    main(), word)  # Skip pure numbers
                and not word.startswith('http')):  # Skip URLs
                product_words.append(word)
        
        # Take meaningful words for product name
        if product_words:
            # Prioritize words that appear later (often product names)
            return ' '.join(product_words[-3:]) if len(product_words) >= 3 else ' '.join(product_words)
        
        return 'Product'
    
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
            
            # Extract title with multiple fallback strategies
            clean_title = None
            
            # Strategy 1: Check for forwarded title patterns in message
            forwarded_title = self.extract_forwarded_title(message_text)
            if forwarded_title:
                clean_title = TitleCleaner.clean_title(forwarded_title)
            
            # Strategy 2: Try scraping from final URL if no forwarded title
            if not clean_title:
                scraped_title = await TitleCleaner.extract_title_from_url(final_url)
                if scraped_title:
                    clean_title = TitleCleaner.clean_title(scraped_title)
            
            # Strategy 3: Extract from URL slug if scraping fails
            if not clean_title:
                url_title = self.extract_title_from_url_slug(final_url)
                if url_title:
                    clean_title = TitleCleaner.clean_title(url_title)
            
            # Strategy 4: Use message text as last resort
            if not clean_title:
                # Remove URL from message text first
                message_without_urls = re.sub(r'https?://\S+', '', message_text).strip()
                if message_without_urls:
                    clean_title = TitleCleaner.clean_title(message_without_urls)
            
            # If still no title, return error
            if not clean_title:
                return "❌ Unable to extract product info"
            
            # Extract price (prioritize message text)
            price = PriceExtractor.extract_price(message_text)
            
            # Check if it's Meesho
            is_meesho = 'meesho.com' in final_url.lower()
            
            # For Meesho, extract size and pin
            size = "All"
            pin = "110001"
            
            if is_meesho:
                # Extract size from message
                size_match = re.search(r'size\s*[-:]?\s*([^\n,]+)', message_text, re.IGNORECASE)
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
    
    def extract_forwarded_title(self, text: str) -> Optional[str]:
        """Extract title from forwarded message text patterns"""
        # Look for patterns like "Product Name @price rs"
        title_price_pattern = r'^([^@]+?)\s*@\d+\s*rs'
        match = re.search(title_price_pattern, text.strip(), re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Look for title on separate line before URL
        lines = text.strip().split('\n')
        for i, line in enumerate(lines):
            if 'http' in line and i > 0:  # URL found, check previous line
                potential_title = lines[i-1].strip()
                # Ensure it's not just domain or empty
                if (potential_title and len(potential_title) > 5 and 
                    not re.search(r'@\d+\s*rs', potential_title) and
                    not potential_title.lower().startswith('http')):
                    return potential_title
        
        return None
    
    def extract_title_from_url_slug(self, url: str) -> Optional[str]:
        """Extract product name from URL slug as fallback"""
        try:
            parsed_url = urlparse(url)
            path = parsed_url.path
            
            # Remove common path prefixes
            path = re.sub(r'^/(?:product|p|dp|item|share)', '', path)
            
            # Extract meaningful parts from path
            path_parts = [part for part in path.split('/') if part and len(part) > 2]
            
            if path_parts:
                # Take the longest part (usually product name)
                product_slug = max(path_parts, key=len)
                
                # Clean up the slug
                product_name = re.sub(r'[-_]', ' ', product_slug)
                product_name = re.sub(r'[^a-zA-Z0-9\s]', ' ', product_name)
                product_name = ' '.join(product_name.split())
                
                # Only return if it looks like a meaningful product name
                if len(product_name) > 5 and not product_name.isdigit():
                    return product_name
            
            return None
            
        except Exception:
            return None
    
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
