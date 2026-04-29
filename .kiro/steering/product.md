# Product Overview

**Pirkei Avot Finder** is a Hebrew-language web application for searching and studying Mishnayot from Pirkei Avot (Ethics of the Fathers). It runs as a fully serverless application on AWS.

## Core Features

- **Multi-modal search**: Chapter/Mishna navigation, exact text search, semantic AI search, tag-based search, and direct mishna number navigation (1-108)
- **Semantic search**: Bedrock Knowledge Base (vector search) + Amazon Nova Pro (LLM reranking) for context-aware Hebrew text understanding
- **Content management**: Admin interface for managing Mishnayot, tags, and categories
- **Tag system**: Hierarchical categorization with color-coded categories
- **Pirush commentary**: Google Docs Viewer integration for PDF pirush documents, with admin toggle

## User Experience

- Hebrew-first interface with RTL support
- Responsive design for mobile and desktop
- Fast search with API Gateway rate limiting (20 requests/minute)
- Visual tag categories with color coding
- Lottie loading animations during API requests
- Gold/dark theme with glassmorphism effects

## Target Audience

Students, teachers, researchers, and anyone studying Pirkei Avot who needs efficient search and navigation capabilities.

## Domain

- Production: `https://pirkei-avot.online`
- CloudFront: `https://dvbs9w4c73suc.cloudfront.net`
