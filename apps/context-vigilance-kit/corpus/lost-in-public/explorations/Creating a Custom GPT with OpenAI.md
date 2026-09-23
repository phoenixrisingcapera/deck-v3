---
title: Creating a Custom GPT with OpenAI
authors:
- Michael Staton
date_created: 2025-04-18
date_modified: 2025-08-22
site_uuid: 56394750-0b7a-498d-8106-b7ea477a990c
tags:
- Explorations
- Fine-Tuners
publish: true
slug: creating-a-custom-gpt-with-openai
at_semantic_version: 0.0.0.1
image_prompt: Two humans are looking like tailors dressing a Robot who is standing
  in front of a mirror at a department store.
banner_image: https://ik.imagekit.io/xvpgfijuw/uploads/lossless/july/Creating_a_Custom_GPT_with_OpenAI_banner_image_1755821734992_eFlk3Mj6-.webp
portrait_image: https://ik.imagekit.io/xvpgfijuw/uploads/lossless/july/Creating_a_Custom_GPT_with_OpenAI_portrait_image_1755821743002_qpXuNUody.webp
square_image: https://ik.imagekit.io/xvpgfijuw/uploads/lossless/july/Creating_a_Custom_GPT_with_OpenAI_square_image_1755821756814__wcudnt62.webp
source_root: /Users/mpstaton/code/lossless-monorepo/content/lost-in-public
source_relative_path: explorations/Creating a Custom GPT with OpenAI.md
source_repo_slug: lost-in-public
collated_at: '2026-08-24'
source_path: "content/lost-in-public/explorations/Creating a Custom GPT with OpenAI.md"
---

## Context
I'm following along to this [[YouTube]] video: [Creating Custom GPTs: API Key For Custom Actions | Complete Guide](https://youtu.be/6P6MQ_j73mI?si=jJGUcygTjmpLa_lA)

Creating a [[Custom GPT]] is like creating a sandbox in which you can apply your own [[concepts/Explainers for AI/Fine Tuning]] to the [[GPT-Series Models]] in [[OpenAI]]

> [!LLM Response] [[GPT-Series Models|GPT's]] Response
> Creating a custom GPT in OpenAI involves using the **Custom GPTs** feature available in the ChatGPT interface. Here’s a step-by-step guide to help you get started:
> 
> ---
> 
> ### **1. Accessing the Custom GPT Feature**
> 
> - Go to [ChatGPT](https://chat.openai.com/)
> - Click on **"Explore GPTs"** in the left sidebar.
> - Click **"Create a GPT"** to open the customization interface.
> 
> ---
> 
> ### **2. Setting Up Your Custom GPT**
> 
> OpenAI provides a guided setup where you define your GPT’s behavior and personality.
> 
> #### **Step 1: Define Your GPT’s Purpose**
> 
> - Give it a name that reflects its purpose (e.g., "News Assistant").
> - Write a description of what your GPT does.
> - Specify its **personality and tone** (e.g., formal, casual, technical).
> 
> #### **Step 2: Configure Instructions**
> 
> - Modify the **"Instructions for the Assistant"** field to customize responses.
> - Adjust **"Instructions for the User"** to guide users on how to interact with your GPT.
> 
> #### **Step 3: Upload APIs & Files (Advanced)**
> 
> - If you want to integrate **GNews API**, you’ll need to use **API calls** within the GPT.
> - You can provide API documentation or a sample request/response format.
> - Upload relevant files (if needed) to help it process news queries efficiently.
> 
> #### **Step 4: Test & Iterate**
> 
> - Use the built-in chat window to test responses.
> - Adjust instructions if needed to improve accuracy and relevance.
> 
> ---
> 
> ### **3. Advanced Customization (API Integration)**
> 
> To integrate the **GNews API**, you’ll need to use external API calls. Since OpenAI’s Custom GPTs do not natively support API calls yet, you may need to:
> 
> 1. **Use an external script** (e.g., Python, Node.js) to fetch data from GNews and send it to the GPT.
> 2. **Integrate with a no-code automation tool** like Zapier or Make.com to pull news from GNews and send it to your chatbot.
> 
> ---
> 
> ### **4. Deployment & Sharing**
> 
> Once you are satisfied:
> 
> - Publish your GPT for personal use.
> - Share the link with others.
> - If applicable, integrate it into a website or app.

The video seems to suggest you can create [[Application Programming Interface|API]] integrations through a feature called [[Actions]]. 
>This video provides a comprehensive guide on how to create custom GPTs with a focus on integrating Auth Actions API Key for applications in the OpenAI App Store. It likely covers the step-by-step process of developing and customizing GPTs, setting up necessary authentication, and preparing them for the OpenAI App Store. SUBSCRIBE for more! 👉 [http://bit.ly/3zlUmiS](https://www.youtube.com/redirect?event=video_description&redir_token=QUFFLUhqbjJKMmxvZ3RrVlJCWmlDN0RRcFpEbmJPQnJaUXxBQ3Jtc0tuU2NldVN4T2xXWUJWVlJHRWUtSXBHUWZQRF9wM0NuUGMzYTlxT28wYk1ENGduY0tXbk5pZ20yZkRfNi1BSThWY3FHQlU1MnFRWlR4ZzVLTWVyTGZIVmJGNENiZ19EakhIU2NNZ191M2xPZG93bHlEMA&q=http%3A%2F%2Fbit.ly%2F3zlUmiS&v=6P6MQ_j73mI) 👈

Here was [[GPT-Series Models|GPT's]] response: 

> [!LLM Response] [[GPT-Series Models|GPT]] Response
> You're looking to create an **Action** for your custom GPT that integrates with the **GNews API**—great choice! 🎯
> 
> Right now, OpenAI hasn't publicly released access for developers to add **Actions** to GPTs in the builder. However, once this feature is available, you'd follow these general steps:
> 
> ### **How Actions Work**
> 
> 1. **Define an API Schema** (OpenAPI/JSON format)
> 2. **Authenticate** (Usually via API keys)
> 3. **Register the Action** in OpenAI’s GPT builder
> 4. **Use the Action** inside your custom GPT
> 
> ### **What You Can Do Now**
> 
> I can help you:  
> ✅ Write an OpenAPI schema for GNews integration  
> ✅ Set up API authentication  
> ✅ Handle API responses and formatting


##### You said:

I would like a Custom GPT that I can access using an API endpoint and my developer API key. I want this Custom GPT to ghost write content for my "wiki" style website, so the responses should follow a distinct format. I have a list of vocabulary words that are Technology and/or business trends, some of which are just the word as the filename, and some of which have some content and links just dumped in, and some of which have a directory of markdown files that are autogenerated by various AI's. How would I create such a Custom GPT?

###### ChatGPT said:

You're describing a **Custom GPT** that:

1. **Generates "wiki-style" content** for tech and business trends.
2. **Can be accessed via API** using OpenAI’s developer API key.
3. **Uses structured formatting** for consistency.
4. **Incorporates existing vocabulary words and markdown files** into responses.

---

### **Approach to Building This**

#### **1. Choosing the Right Setup**

- OpenAI's **Assistants API** allows you to programmatically interact with a fine-tuned GPT for your use case.
- If OpenAI’s **GPT Actions** become available, you could directly integrate external data.

#### **2. Structuring the API-Powered GPT**

Since OpenAI doesn’t yet allow Custom GPTs to have their own API endpoints, you would:

1. **Use the Assistants API** (or GPT-4-turbo) to build your custom writing assistant.
2. **Host your own API wrapper** to format requests and integrate with your vocabulary files.
3. **Define a strict output format** for consistency across articles.

---

### **Implementation Plan**

#### **1. Define the Wiki Content Format**

Example of structured output for each entry:

```markdown
# {Topic Name}  

## Definition  
A brief and clear definition.  

## History & Evolution  
How the concept has evolved over time.  

## Current Trends  
Notable companies, influencers, or major developments.  

## Use Cases  
Practical applications and industries involved.  

## References & Further Reading  
- [External Link 1](#)  
- [External Link 2](#)  

```

Would this format work, or do you have specific requirements?

---

#### **2. Processing Existing Vocabulary & Markdown Files**

Since you have:

- Standalone words as filenames
- Words with content and links
- AI-generated markdown files

Your pipeline should:

- **Extract text & metadata** from existing files.
- **Provide context** to the GPT via API calls.
- **Ensure consistent formatting** by refining responses.

Would you like help writing a **script to process these files** before feeding them to GPT?

---

#### **3. API Integration & Automation**

To make your GPT accessible via API, you’d:

1. **Use OpenAI’s Assistants API** to interact with the model programmatically.
2. **Automate content generation** with a script that:
    - Takes a topic from your vocabulary list.
    - Checks if content already exists.
    - Generates missing sections using GPT.
    - Stores the output in markdown format.
3. **Deploy an endpoint** (e.g., FastAPI or Flask) so other services can request content.

Would you like me to generate Python code to:  
✅ Fetch wiki-style content via OpenAI API  
✅ Auto-process vocabulary words  
✅ Format and store results in markdown?

---

💡 **Next Steps:** Let me know if you want the code or need adjustments to the structure! 🚀

***
## My Template
```markdown
Who or what organization is credited for discoverying, creating, or coining this term, category, invention, etc. 

If there was a "creator" or a person who coined the term, make sure to mention them inside a backlink `\[\[`${P} `\]\]`
```