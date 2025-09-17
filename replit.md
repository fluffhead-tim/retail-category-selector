# Overview

This is a Retail Category Selector API that automatically categorizes retail products across multiple marketplace taxonomies using LLM-powered classification. The system takes product data (name, description, brand, etc.) and maps it to the most appropriate leaf categories in various marketplace taxonomies like Tesco, B&Q, SuperDrug, Mountain Warehouse, Debenhams, and Decathlon. The API is designed for automated product categorization when publishing from a main catalog to different marketplaces.

## Demo UI

A user-friendly web interface has been added for non-technical demos. The UI allows users to paste product JSON descriptions, select marketplaces, and view categorization results in a clean, responsive interface built with Tailwind CSS.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend Framework
- **Flask-based REST API** with health check and categorization endpoints
- **Pydantic models** for request/response validation and data serialization
- **Modular architecture** with clear separation between API layer, core business logic, and configuration
- **Static UI serving** for demo interface with proper path resolution

## Frontend Demo Interface
- **Tailwind CSS UI** with mobile-first responsive design
- **Single-page application** for product categorization testing
- **Real-time API integration** with proper error handling and loading states
- **JSON input/output** with copy-to-clipboard functionality
- **Marketplace selection** with dropdown for all available marketplaces

## Core Components

### Product Classification Engine
- **Two-stage classification process**: Initial heuristic scoring followed by LLM-powered final selection
- **Configurable pre-filtering** to reduce token usage by shortlisting top candidates before LLM processing
- **Multi-marketplace support** with different taxonomy structures and field mappings
- **Robust parsing** with HTML stripping and text normalization for product descriptions

### Taxonomy Management
- **File-based taxonomy storage** in JSON format for each marketplace
- **Hierarchical path resolution** with automatic leaf node identification
- **Flexible field mapping** supporting different marketplace schema conventions (id/name vs displayName/code)
- **Path-based scoring** using keyword matching and depth weighting

### LLM Integration
- **Multi-provider support** (OpenAI GPT-4o-mini, Anthropic Claude-3.5-Sonnet)
- **Structured JSON responses** with fallback parsing for malformed outputs
- **Token-aware processing** with configurable text truncation limits
- **Error handling** with graceful degradation to "UNMAPPED" categories

## Data Architecture

### Configuration Management
- **Environment-based configuration** with .env file support
- **Centralized configuration module** for API keys, model selection, and file paths
- **Runtime parameter tuning** via environment variables (shortlist limits, character limits, debug mode)
- **Port configuration** with environment variable override support

### Marketplace Data Structure
- **JSON-based marketplace definitions** with taxonomy file references and API endpoints
- **Standardized leaf node format** with id, name, path, and depth metadata
- **Fuzzy matching capabilities** using RapidFuzz for similarity scoring

## API Design
- **RESTful endpoints** with health check and single categorization route
- **Flexible input processing** supporting various product data formats with automatic field mapping
- **Comprehensive error handling** with detailed validation messages
- **Static file serving** for demo UI integration
- **CORS-ready** for frontend integration

# External Dependencies

## LLM Providers
- **OpenAI API** for GPT-4o-mini model access
- **Anthropic API** for Claude-3.5-Sonnet model access

## Python Libraries
- **Flask 3.0.3** - Web framework for API endpoints and static serving
- **Pydantic 2.8.2** - Data validation and serialization
- **httpx 0.27.2** - Async HTTP client for external API calls
- **RapidFuzz 3.9.6+** - Fast string matching and similarity scoring
- **orjson 3.10.7+** - High-performance JSON parsing
- **Pillow 10.4.0** - Image processing capabilities
- **Gunicorn 21.2+** - WSGI HTTP server for production deployment

## Development Tools
- **Bruno API testing** - Collection for API endpoint testing across environments
- **Demo UI** - HTML/Tailwind CSS interface for non-technical product categorization testing

## Data Sources
- **Marketplace taxonomy files** - JSON hierarchies for Tesco, B&Q, SuperDrug, Mountain Warehouse, Debenhams, and Decathlon
- **Category prompts** - Markdown-based system prompts for LLM classification instructions

# Recent Changes

## September 17, 2025 - Demo UI Implementation
- Added user-friendly web interface in `ui/` folder for non-technical demos
- Implemented Flask static file serving with proper path resolution using pathlib
- Created responsive Tailwind CSS interface with JSON input, marketplace selection, and results display
- Added comprehensive error handling and loading states for better UX
- Configured workflow on port 8000 to avoid port conflicts while maintaining functionality
- Integrated real-time API calls with same-origin fetch to avoid CORS issues