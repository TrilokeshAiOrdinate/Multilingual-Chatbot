"""
Test Suite & Demo for Legal Orchestrator Agent
Run this to test the complete pipeline
"""

import json
import sys
from typing import Dict, Any

try:
    from orchestrator import orchestrator
except ImportError as e:
    print(f"❌ Error: Could not import orchestrator: {e}")
    print("Make sure all dependencies are installed: pip install -r requirements.txt")
    sys.exit(1)


# =============================================================================
# TEST QUERIES
# =============================================================================

TEST_QUERIES = [
    {
        "name": "Term Definition Query",
        "query": "What is negligence in Indian law?",
        "language": "en",
        "description": "Test law dictionary tool for legal term definitions"
    },
    {
        "name": "Live Case Query",
        "query": "Show me case CNR 2024/12345",
        "language": "en",
        "description": "Test eCourts tool for live case lookup (will return mock data)"
    },
    {
        "name": "Historical Case Query",
        "query": "Tell me about landmark negligence cases",
        "language": "en",
        "description": "Test MasterDB tool for historical cases and precedents"
    },
    {
        "name": "Mixed Query",
        "query": "Has case CNR 2024/12345 applied the 2015 negligence precedent?",
        "language": "en",
        "description": "Test orchestrator combining multiple tools"
    },
    {
        "name": "Complex Legal Concept",
        "query": "Explain the difference between tort and contract law with recent case examples",
        "language": "en",
        "description": "Test complex query routing"
    },
]


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def print_header(text: str, char: str = "═"):
    """Print formatted header"""
    width = 80
    print(f"\n{char * width}")
    print(f"  {text.upper()}")
    print(f"{char * width}\n")


def print_section(text: str):
    """Print formatted section"""
    print(f"\n{'─' * 80}")
    print(f"  {text}")
    print(f"{'─' * 80}\n")


def print_result(result: Dict[str, Any]):
    """Print formatted result"""
    print(f"Status: {result.get('status', 'unknown').upper()}")
    print(f"Query: {result.get('query', 'N/A')}")
    print(f"Tools Used: {', '.join(result.get('tools_used', []))}")
    print(f"Sources: {result.get('sources_count', 0)}")
    
    if result.get('response'):
        print(f"\n{'─' * 40} RESPONSE {'─' * 40}")
        print(result.get('response'))
        print(f"{'─' * 80}")
    
    if result.get('error'):
        print(f"\n❌ ERROR: {result.get('error')}")


def test_single_query(query: str, language: str = "en") -> Dict[str, Any]:
    """Test a single query"""
    print(f"Processing: {query[:70]}...")
    
    try:
        result = orchestrator.process_query(
            user_query=query,
            language=language,
            return_format="markdown"
        )
        return result
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "query": query
        }


def test_multiple_formats(query: str) -> Dict[str, Dict[str, Any]]:
    """Test same query with different output formats"""
    print(f"Testing query with multiple formats...")
    
    formats = ["markdown", "json", "html"]
    results = {}
    
    for fmt in formats:
        try:
            result = orchestrator.process_query(
                user_query=query,
                language="en",
                return_format=fmt
            )
            results[fmt] = result
        except Exception as e:
            results[fmt] = {"status": "error", "error": str(e)}
    
    return results


def test_available_tools():
    """Test tool registry"""
    print("Available Tools:")
    tools = orchestrator.get_available_tools()
    
    for i, (tool_name, description) in enumerate(tools.items(), 1):
        print(f"  {i}. {tool_name}")
        print(f"     └─ {description}")


# =============================================================================
# TEST SUITES
# =============================================================================

def test_basic_queries():
    """Run basic test queries"""
    print_header("TEST SUITE 1: BASIC QUERIES")
    
    for i, test in enumerate(TEST_QUERIES[:3], 1):
        print_section(f"Test {i}: {test['name']}")
        print(f"Description: {test['description']}")
        print(f"Query: {test['query']}\n")
        
        result = test_single_query(test['query'], test['language'])
        print_result(result)
        print()


def test_mixed_queries():
    """Run mixed/complex queries"""
    print_header("TEST SUITE 2: COMPLEX QUERIES")
    
    for i, test in enumerate(TEST_QUERIES[3:], 1):
        print_section(f"Complex Test {i}: {test['name']}")
        print(f"Query: {test['query']}\n")
        
        result = test_single_query(test['query'], test['language'])
        print_result(result)
        print()


def test_output_formats():
    """Test different output formats"""
    print_header("TEST SUITE 3: OUTPUT FORMATS")
    
    query = "What is negligence?"
    print_section(f"Testing: {query}")
    
    results = test_multiple_formats(query)
    
    for fmt, result in results.items():
        print(f"\n📄 Format: {fmt.upper()}")
        print(f"Status: {result.get('status', 'unknown')}")
        if result.get('status') == 'success':
            response = result.get('response', '')
            print(f"Response preview: {response[:150]}...")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
        print()


def test_edge_cases():
    """Test edge cases and error handling"""
    print_header("TEST SUITE 4: EDGE CASES")
    
    edge_cases = [
        {"query": "?", "description": "Very short/invalid query"},
        {"query": "", "description": "Empty query"},
        {"query": "x" * 1000, "description": "Extremely long query"},
        {"query": "123 456 789", "description": "Numbers only"},
    ]
    
    for i, test in enumerate(edge_cases, 1):
        print_section(f"Edge Case {i}: {test['description']}")
        print(f"Query: {test['query'][:50]}...")
        
        try:
            result = test_single_query(test['query'])
            print(f"Status: {result.get('status', 'unknown')}")
            if result.get('error'):
                print(f"Error handled: {result.get('error')}")
        except Exception as e:
            print(f"Exception caught: {str(e)}")
        print()


def test_performance():
    """Test performance metrics"""
    print_header("TEST SUITE 5: PERFORMANCE")
    
    import time
    
    queries = [
        "What is negligence?",
        "Define contract",
        "What is tort?",
    ]
    
    print("Measuring response times...\n")
    
    times = []
    for i, query in enumerate(queries, 1):
        start = time.time()
        result = test_single_query(query)
        elapsed = time.time() - start
        times.append(elapsed)
        
        print(f"Query {i}: {elapsed:.2f}s")
    
    avg_time = sum(times) / len(times)
    print(f"\n📊 Performance Summary:")
    print(f"  Average time: {avg_time:.2f}s")
    print(f"  Min time: {min(times):.2f}s")
    print(f"  Max time: {max(times):.2f}s")


# =============================================================================
# INTERACTIVE MODE
# =============================================================================

def interactive_mode():
    """Interactive query mode"""
    print_header("INTERACTIVE MODE")
    print("Enter legal queries (type 'exit' or 'quit' to stop)\n")
    
    query_count = 0
    
    while True:
        try:
            print_section(f"Query #{query_count + 1}")
            user_query = input("Enter your legal query: ").strip()
            
            if user_query.lower() in ['exit', 'quit']:
                print("\n👋 Goodbye!")
                break
            
            if not user_query:
                print("⚠️  Please enter a valid query")
                continue
            
            language = input("Language (en/hi/ta/etc.) [default: en]: ").strip() or "en"
            
            result = test_single_query(user_query, language)
            print_result(result)
            
            query_count += 1
            
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted by user. Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            continue


# =============================================================================
# MAIN MENU
# =============================================================================

def print_menu():
    """Print main menu"""
    print_header("LEGAL ORCHESTRATOR AGENT - TEST SUITE")
    print("""
Available Test Suites:

  1. Basic Queries (Term, Live Case, Historical)
  2. Complex Mixed Queries
  3. Output Format Testing (Markdown, JSON, HTML)
  4. Edge Cases & Error Handling
  5. Performance Metrics
  6. Interactive Mode
  7. View Available Tools
  8. Run All Tests
  0. Exit

    """)


def main():
    """Main test runner"""
    
    while True:
        print_menu()
        
        try:
            choice = input("Select test suite (0-8): ").strip()
            
            if choice == "1":
                test_basic_queries()
            elif choice == "2":
                test_mixed_queries()
            elif choice == "3":
                test_output_formats()
            elif choice == "4":
                test_edge_cases()
            elif choice == "5":
                test_performance()
            elif choice == "6":
                interactive_mode()
            elif choice == "7":
                print_header("Available Tools")
                test_available_tools()
            elif choice == "8":
                print_header("Running All Tests")
                test_basic_queries()
                test_mixed_queries()
                test_output_formats()
                test_edge_cases()
                print("\n✅ All tests completed!")
            elif choice == "0":
                print("\n👋 Exiting. Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please select 0-8.")
            
            input("\nPress Enter to continue...")
        
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


# =============================================================================
# QUICK TEST (if run directly)
# =============================================================================

if __name__ == "__main__":
    try:
        # Run quick test
        if len(sys.argv) > 1 and sys.argv[1] == "quick":
            print_header("Quick Test")
            result = test_single_query("What is negligence?")
            print_result(result)
        else:
            # Run interactive menu
            main()
    
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
