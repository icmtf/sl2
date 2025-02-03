import streamlit as st
import yaml
from typing import Dict, List

def configure_page():
    st.set_page_config(
        page_title="CodeHorizon - Home",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

def load_bookmarks() -> Dict[str, List[Dict[str, str]]]:
    with open('views/home/links.yaml', 'r') as file:
        return yaml.safe_load(file)

def get_css():
    return """
    <style>
        .bookmark-container {
            padding: 1rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
            transition: all 0.3s ease;
            position: relative;
            background-color: #1e1e1e;
            border: 1px solid #333;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        .bookmark-container:hover {
            transform: translateY(-3px);
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.2);
            border-color: #666;
        }
        
        .bookmark-header {
            display: flex;
            align-items: center;
            margin-bottom: 0.5rem;
        }
        
        .bookmark-icon {
            width: 24px;
            height: 24px;
            margin-right: 0.5rem;
        }
        
        .bookmark-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin: 0;
            color: #ffffff;
            text-decoration: none;
        }
        
        .bookmark-description {
            font-size: 0.9rem;
            line-height: 1.4;
            margin: 0.5rem 0;
            color: #b0b0b0;
        }
        
        .bookmark-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 0.5rem;
        }
        
        .bookmark-tag {
            font-size: 0.8rem;
            padding: 0.2rem 0.6rem;
            border-radius: 12px;
            background-color: #333;
            color: #fff;
        }
        
        .category-title {
            font-size: 1.3rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid #666;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
    </style>
    """

def get_all_tags(bookmarks: Dict[str, List[Dict[str, str]]]) -> List[str]:
    """Extract all unique tags from bookmarks"""
    tags = set()
    for category_data in bookmarks.values():
        for link in category_data['links']:
            tags.update(link.get('tags', []))
    return sorted(list(tags))

def filter_bookmarks(bookmarks: Dict[str, List[Dict[str, str]]], search_query: str, selected_tags: List[str]) -> Dict[str, List[Dict[str, str]]]:
    """Filter bookmarks based on search query and tags"""
    if not search_query and not selected_tags:
        return bookmarks
        
    filtered_bookmarks = {}
    
    for category, category_data in bookmarks.items():
        filtered_links = []
        for link in category_data['links']:
            # Check if link has all selected tags
            if selected_tags:
                link_tags = set(link.get('tags', []))
                if not all(tag in link_tags for tag in selected_tags):
                    continue
            
            # If there is a search query, check if it matches
            if search_query:
                search_query = search_query.lower()
                # Search in name
                if search_query in link['name'].lower():
                    filtered_links.append(link)
                    continue
                    
                # Search in description
                if search_query in link['description'].lower():
                    filtered_links.append(link)
                    continue
                    
                # Search in tags
                if any(search_query in tag.lower() for tag in link.get('tags', [])):
                    filtered_links.append(link)
                    continue
            else:
                filtered_links.append(link)
                
        if filtered_links:
            filtered_bookmarks[category] = {
                'icon': category_data['icon'],
                'links': filtered_links
            }
            
    return filtered_bookmarks
def convert_material_icon(icon: str) -> str:
    """Convert material icon notation to unicode character"""
    # Remove colons and convert to emoji format
    icon = icon.replace(':', '').replace('/', '_')
    return f':{icon}:'


def on_change():
    st.session_state.update_counter = st.session_state.get('update_counter', 0) + 1

def main():
    st.markdown(get_css(), unsafe_allow_html=True)
    
    st.title("CodeHorizon Hub")
    
    # Load bookmarks and get all tags
    bookmarks = load_bookmarks()
    all_tags = get_all_tags(bookmarks)
    
    # Create two columns for search and tags
    search_col, tags_col = st.columns([2, 1])
    
    with search_col:
        # Search field
        search_query = st.text_input("🔍 Search bookmarks...", placeholder="Press Enter to apply")
    
    with tags_col:
        # Tags multiselect
        selected_tags = st.multiselect(
            "Filter by tags",
            options=all_tags,
            default=[]
        )
    
    # Filter bookmarks
    filtered_bookmarks = filter_bookmarks(bookmarks, search_query, selected_tags)
    
    # Create columns
    num_columns = 4
    cols = st.columns(num_columns)
    
    # Distribute categories across columns
    categories = list(filtered_bookmarks.keys())
    for i, category in enumerate(categories):
        col_index = i % num_columns
        with cols[col_index]:
            category_data = filtered_bookmarks[category]
            icon = convert_material_icon(category_data['icon'])
            st.markdown(f"### {icon} {category}")
            
            for bookmark in category_data['links']:
                card_html = f"""
                <div class="bookmark-container">
                    <div class="bookmark-header">
                        <img src="{bookmark['icon']}" class="bookmark-icon" onerror="this.src='https://www.google.com/favicon.ico'">
                        <a href="{bookmark['url']}" target="_blank" class="bookmark-title">
                            {bookmark['name']}
                        </a>
                    </div>
                    <div class="bookmark-description">
                        {bookmark['description']}
                    </div>
                    <div class="bookmark-tags">
                        {' '.join(f'<span class="bookmark-tag">#{tag}</span>' for tag in bookmark.get('tags', []))}
                    </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)

if __name__ == "__main__":
    configure_page()
    main()