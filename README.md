# n8n Helium 10 Python  Automation (ASIN → CSV → Google Sheets)

## Workflow Image
<img width="1268" height="622" alt="n8n-helium10-browser-automation" src="https://github.com/user-attachments/assets/1d7a9b19-a081-4bb3-9bbc-13eba8e06be8" />

## Overview
This project is an end-to-end automation system that replaces hours of manual keyword tracking with a fully orchestrated workflow. Using n8n as the automation backbone, the workflow connects Google Sheets, Python scripting, and browser automation to reliably extract and organize keyword ranking data for a large set of Amazon ASINs.

## How It Works
At a high level, the system starts by pulling a list of ASINs directly from a Google Sheet, which acts as the central source of truth for product tracking. These ASINs are collected into an array and passed as arguments to a custom Python script. The script then drives browser automation to log in to Helium 10 — a leading Amazon seller platform that provides tools for product research, keyword tracking, and competitor analysis. Through this integration, the system navigates to Helium 10’s Keyword Tracker, searches for each product’s keywords, and automatically downloads the corresponding CSV reports. Each CSV is saved locally for downstream analysis.

## Highlights
- **n8n Orchestration:** Automates the entire process with a trigger-to-execution pipeline, eliminating the need for manual intervention.  
- **Google Sheets Integration:** Dynamically fetches ASINs from a live spreadsheet, allowing non-technical users to update tracking targets without touching code.  
- **Python Automation:** A robust script (with CLI support) that handles authentication, browser navigation, and CSV file downloads.  
- **Scalable Design:** Capable of processing dozens of ASINs in one run, scaling from small daily updates to bulk keyword tracking for hundreds of products.  
- **Time Savings:** What used to take a person multiple hours of repetitive clicking and downloading is now completed automatically in under an hour, freeing up time for strategic analysis instead of data collection.

## Impact
This project demonstrates strong skills in workflow automation, API/browser scripting, and system integration. It also showcases an ability to translate real business pain points into technical solutions that save time, reduce errors, and increase reliability.
