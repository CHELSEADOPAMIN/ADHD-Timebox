

# ADHD Timebox Agent

As a developer who also has ADHD, I know the pain points of this brain type: it's not that we don't *want* to do things, but we struggle with prioritizing, getting started, and getting lost when switching tasks.

To solve this, I built the **ADHD Timebox Agent** based on the **ConnectOnion framework**. This isn't just a normal To-Do List; it is a full-process execution coach based on the "Timeboxing" methodology. It doesn't just record tasks—it acts as an AI agent that takes over my "prefrontal cortex" functions: planning, supervising execution, and providing dopamine feedback.

## 🚀 Quick Start

### 1. Environment Setup

Ensure your system has Python 3.10 or higher installed.

```bash
# Clone the repository
git clone <repository_url>
cd ADHD-Timebox

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

```

### 2. Install Dependencies

```bash
pip install -r requirements.txt

```

### 3. Configure Credentials

#### Google Calendar Credentials

To let the Agent manage your calendar, you need to configure the Google Calendar API:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and create a project.
2. Enable the **Google Calendar API**.
3. Create **OAuth 2.0 Client IDs** (Desktop app).
4. Download the JSON credential file, rename it to `credentials.json`, and place it in the project root directory.
5. On the first run, a browser window will pop up for authorization, creating a `token.json` file automatically.

#### LLM API Key

This project uses the `connectonion` framework to connect to LLMs. You need to configure the API Key (e.g., Gemini, OpenAI).
Set environment variables or create a `.env` file:

```bash
export GEMINI_API_KEY="your_api_key_here"
# OR
export OPENAI_API_KEY="your_api_key_here"

```

*(The specific model is configured as `co/gemini-3-pro-preview` in `backend/main.py`. Ensure you have access or change it to another model in the code).*

#### Frontend Auth (Clerk)

This app uses Clerk for Google/Apple sign-in. You only need Clerk keys in `.env`:

```bash
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY="your_publishable_key"
CLERK_SECRET_KEY="your_secret_key"
```

Enable Google/Apple in the Clerk dashboard. No provider client IDs are required in this repo.

### 4. Start the Agent

#### Multi-Agent System (MAS)

This mode includes the full "Plan-Monitor-Reward" loop.

```bash
python backend/main_mas.py

```

**Features**:

* **Orchestrator**: The central router. It identifies if you need to plan, start focusing, or if you have a sudden distracting thought.
* **Focus Agent**: Your companion during deep work. It detects if you are getting distracted.
* **Idle Watcher**: (Requires permissions) Monitors computer idle status to remind you to return to the task.
* **Parking Lot**: A "Save for later" feature. It stores distracting thoughts so they don't break your current flow.

## 📂 Directory Structure

* `backend/adhd_brain/`: The Agent's "Brain". Stores memories, logs, and generated plan files.
* `backend/agents/`: Code for each specific agent (Focus, Planner, Reward, etc.).
* `backend/tools/`: Utility tools (Calendar tools, idle detection, etc.).
* `backend/main_mas.py`: Entry point for the Multi-Agent mode.

## ❓ FAQ

**Q: `ModuleNotFoundError: No module named 'connectonion'`?**
A: Make sure you activated your virtual environment and ran `pip install -r requirements.txt`.

**Q: Calendar isn't syncing?**
A: Check if `credentials.json` exists. On the first run, you must manually authorize it in the browser.

**Q: How do I change the AI model?**
A: Open `backend/main_mas.py` (or the specific agent file), find `model="co/gemini-3-pro-preview"`, and change it to a model name supported by `connectonion` (e.g., `gpt-4o`, `claude-3-5-sonnet`).

---

# ADHD-Timebox: Project Details

### I. Introduction

**ADHD Timebox Agent** is an AI assistant designed to help people with ADHD effectively use the **Timeboxing** method. It addresses common ADHD problems like "difficulty prioritizing," "trouble starting," "time blindness," and "interrupted execution." It lowers cognitive load to help users enter and stay in a "Flow State."

### II. What is Timeboxing?

##### 1. Core Definition

**Timeboxing** is a method where you lock a single task into a **specific time slot**.
It’s not just a list; it **binds a task to a specific time**. Crucially, you **must produce a result within that time**. It’s like locking a task in a box: you define the start and end time, and **you only do that one thing inside the box**.

*(Elon Musk reportedly uses timeboxing to achieve 8x the workload of an average person).*

##### 2. How to Execute?

**Step 1: Box it (Planning Phase)**

* **List it:** List all tasks before the day starts.
* **Pick the best:** Select only the **top 3-5 most important tasks**. Don't try to do everything.
* **Set time:** Put them on the calendar with clear start/end times (e.g., 15, 30, or 60 minutes).

**Step 2: Close the Box (Execution Phase)**

* **Start on time:** Even if you don't want to, start at the scheduled minute. Even a micro-action (like opening a document) counts.
* **Single Core:** Remove phones/distractions. Focus on one thing. Do not question the plan; just execute.

**Step 3: Open the Box (Review Phase)**

* **Stop on time:** When time is up, stop. Don't chase perfection; aim for "acceptable."
* **Celebrate:** Cross it off the list or eat a snack. Give your brain positive feedback.

##### 3. Core Rules

1. **Use Verbs:** "Write Report" (not just "Report").
2. **Imperfect is fine:** The goal is "Done," not "Perfect."
3. **Trust the Box:** Don't waste energy wondering "Is this the right thing to do?" Just do it.
4. **Box your Rest:** Rest is for recovery. Schedule 5-10 minute "Rest Boxes."
5. **Break it down:**
* Huge task -> Break into steps (e.g., "Annual Report" becomes "Gather Data," "Analyze," "Write Summary").
* Tiny tasks -> Group them together (e.g., "Reply to emails" + "File sorting" = one box).



##### 4. Why it works

* **Fights Parkinson's Law:** Work expands to fill the time available. Limits force efficiency.
* **Saves Brain Power:** You plan once, so you don't have to make decisions all day.
* **Control:** You aren't pushed by events; you control your time.

---

### III. Design Philosophy & Core Decisions

Every design decision in the **ADHD Timebox Agent** is based on the science of Timeboxing. For an ADHD brain, simply "making a list" often fails. The system uses a **Multi-Agent Collaboration Architecture**:

#### 1. Orchestrator Agent (The Boss)

**Role:** The system's brain and router.

* **Intent Recognition:** Listens to what you say and sends you to the right Agent (Plan, Focus, or Reward).
* **Agent Lock:** When a specific Agent (like the Planner) is doing a complex job, the Orchestrator "locks" the conversation to that Agent so the context doesn't get lost.

#### 2. Plan Agent (The Organizer)

**Role:** Your external "Prefrontal Cortex."

* **List to Timebox:** You just dump your messy thoughts ("Write code, learn English, buy groceries"). The Agent organizes them into 15/30/60 minute boxes.
* **Task Shaping:**
* Turns nouns into Verbs.
* Breaks big tasks down and merges small tasks.
* **Syncs directly to Google Calendar.**


* **Dynamic Rescheduling:** If you say "Push everything back 30 minutes," it automatically adjusts your whole schedule so you don't feel like you failed.

#### 3. Focus Agent (The Guardian)

**Role:** Protects your Flow State.

* **Micro-steps:** If you are procrastinating, it suggests tiny steps (e.g., "Just open the file") to bypass anxiety.
* **Thought Parking Lot:** If you suddenly think "I need to check if my camera fits in my bag," the Agent searches for you or saves the note *without* you leaving your work window.
* **Distraction Detection:** Monitors your mouse/keyboard. If you are idle for 5 minutes, it gently reminds you to come back.

#### 4. Reward Agent ( The Cheerleader)

**Role:** Provides Dopamine.

* **Instant Feedback:** Celebrates when you finish a task.
* **Visuals:** Generates fun ASCII art (like cows or animals) to give you a sense of achievement.

---

### IV. Technical Challenges & Solutions

#### 1. From "God Prompt" to Multi-Agent

*Challenge:* Originally, one giant prompt tried to do everything. It was expensive and fragile.
*Solution:* Split into **Orchestrator, Plan, Focus, and Reward**. Each agent is small, specialized, and easier to manage.

#### 2. From Agents to Tools

*Challenge:* Switching to a separate "Note-taking Agent" just to write down a thought was too slow and broke the user's focus.
*Solution:* I turned features into **Tools**. Now, the Focus Agent can use a "Parking Lot Tool" to save a note without leaving the conversation.

#### 3. Fixing Context Drift (State Machine)

*Challenge:* In long conversations, the main Orchestrator would forget who you were talking to (e.g., thinking "9:00 PM" was a new command rather than an answer to the Planner).
*Solution:* Implemented a **Sticky Session / Lock Mechanism**. If the Planner asks a question, the Orchestrator forces the next reply to go back to the Planner, ignoring other logic until the task is done.

#### 4. The "Amnesia" Problem

*Challenge:* When the program restarted, the Agent forgot the plan it just made.
*Solution:* **State Injection.** Before every message, the code reads the current schedule from the disk and "injects" it into the Agent's prompt. The Agent always knows the real-time status of your day.

#### 5. Adding Long-Term Memory

*Challenge:* The system could remember tasks, but not *user preferences* (e.g., "I get tired at 2 PM").
*Solution:* Added **ConnectOnion Memory**. Now, the Plan Agent can leave a "sticky note" for the Focus Agent saying: *"User is stressed today, be gentle."* The system learns your habits over time.

---

### V. Summary

The **ADHD Timebox Agent** uses the power of ConnectOnion's Memory and Multi-Agent orchestration to turn a mechanical schedule into a smart, empathetic partner. It has memory, intuition, and helps my brain function better.




---
---


# ADHD Timebox Agent

作为一个开发者，同时也是 ADHD 人群的一员，我深知这种大脑的痛点：并非不想做，而是优先级混乱、启动困难以及极易在任务切换中迷失。
为了解决这个问题，我基于 ConnectOnion 框架开发了 ADHD Timebox Agent。这不是一个普通的 To-do List，而是一个基于“时间盒”方法论的全流程执行教练。它不仅仅是记录任务，更是通过 AI 代理接管了我的“前额叶皮层”功能——负责规划、监督执行，并提供多巴胺反馈。

## 🚀 快速开始

### 1. 环境准备

确保你的系统已安装 Python 3.10 或更高版本。

```bash
# 克隆仓库 (如果你是从 GitHub 下载)
git clone <repository_url>
cd ADHD-Timebox

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置凭证

#### Google Calendar 凭证
为了让 Agent 管理你的日历，你需要配置 Google Calendar API：
1.  前往 [Google Cloud Console](https://console.cloud.google.com/) 创建一个项目。
2.  启用 **Google Calendar API**。
3.  创建 **OAuth 2.0 Client IDs** (Desktop app)。
4.  下载 JSON 凭证文件，重命名为 `credentials.json` 并放置在项目根目录（或 `ConnectOnion/` 目录下，取决于库的配置，建议放在根目录）。
5.  首次运行时，系统会弹出浏览器窗口进行授权，授权后会生成 `token.json`。

#### LLM API Key
本项目使用 `connectonion` 框架连接大模型。你需要配置相应的 API Key（例如 Gemini、OpenAI 等）。
请设置环境变量或创建 `.env` 文件（如果支持）：
```bash
export GEMINI_API_KEY="your_api_key_here"
# 或
export OPENAI_API_KEY="your_api_key_here"
```
*(具体使用的模型在 `backend/main.py` 中配置为 `co/gemini-3-pro-preview`，请确保你有访问权限或在代码中修改为其他模型)*

### 4. 启动 Agent

#### 多智能体系统 (MAS)
包含完整的“执行-监测-奖励”闭环。

```bash
python backend/main_mas.py
```
**功能**：
- **Orchestrator**: 中央路由，识别你是要规划、还是要开始专注、或者是突然有了杂念。
- **Focus Agent**: 专注时的伴侣，检测走神。
- **Idle Watcher**: (需要额外权限) 监测电脑空闲状态，提醒你回到任务。
- **Parking Lot**: "记一下..." 功能，把干扰想法暂存，不打断当前心流。

## 📂 目录结构说明

- `backend/adhd_brain/`: Agent 的“大脑”，存储记忆、日志和生成的计划文件。
- `backend/agents/`: 各个智能体的实现代码 (Focus, Planner, Reward 等)。
- `backend/tools/`: 实用工具集 (日历工具、空闲检测等)。
- `backend/main_mas.py`: 多智能体模式入口。

## ❓ 常见问题

**Q: 启动时报错 `ModuleNotFoundError: No module named 'connectonion'`?**
A: 请确保你已激活虚拟环境并运行了 `pip install -r requirements.txt`。

**Q: 日历无法同步？**
A: 请检查 `credentials.json` 是否存在且有效。首次运行需要手动在浏览器中点击授权。

**Q: 如何修改使用的 AI 模型？**
A: 打开 `backend/main.py` (单体) 或 `backend/agents/orchestrator.py` (MAS)，找到 `model="co/gemini-3-pro-preview"` 并修改为你支持的模型名称 (如 `gpt-4o`, `claude-3-5-sonnet` 等，需 `connectonion` 支持)。

---

# ADHD-Timebox

### 一. 项目简介

**ADHD Timebox Agent 是一个帮助 ADHD人群 有效的使用时间盒设计的AI辅助系统。它不仅仅是一个待办清单，更是一个基于“时间盒”** 方法论的全流程执行教练。

**ADHD Timebox Agent** 通过Plan、Focus、Rewards 多个agent 配合多个tools ，解决 ADHD 人群常见的“优先级难划分”、“启动困难”、“时间盲区”和“执行中断”问题，通过降低认知负荷，帮助用户进入并保持心流状态。


### 二.时间盒
##### 1. 核心定义
**时间盒**是一种将任务「锁」进**特定时间段**的**单任务管理方法**。
它不是普通的 To-do List，而是**把任务与具体时间点绑定**。
而且要求**在规定时间内必须产出成果**。就像把任务关进一个个「盒子」里， 规定好开始和结束时间，  最重要的是**在这个盒子里只做这一件事**。

马斯克用时间盒管理法 一年完成的工作量，几乎是别人的八倍。
##### 2.怎么执行时间盒？
执行分为 **计划阶段** 、**执行阶段**和验收阶段 。
######  第一步：装盒（计划阶段）
- **列清单**  
  在每天开始前，列出所有待办事项。
- **挑重点**  
  只挑出 **最重要的 3–5 项任务**，而不是试图做完所有事。
- **定时间**  
  把任务填入日程表，设定明确的起止时间。  
  常见规格：**15 分钟 / 30 分钟 / 60 分钟**。
---
###### 第二步：封盒（执行阶段）
- **准时开启**  
  即使不想做，也要准时开始，  
  哪怕只是一个微小的启动动作（例如：打开文档）。
- **单核工作**  
  移除手机等干扰，一次只专注一件事。  
  不质疑计划，不中途切换任务。
---
###### 第三步：开盒（验收阶段）
- **准时结束**  
  时间一到就停止，  
  不追求完美，只要达到「可接受标准」。

- **简单庆祝**  
  划掉清单或奖励自己（比如吃点零食），  
  给大脑一个正向反馈。

---
##### 3、时间盒的核心规则
为了保证时间盒真正有效，需要遵守以下规则：

1. **动词导向**  
   任务要用动词描述（如「撰写报告」而不是「报告」）。

2. **不求完美**  
   目标是在有限时间内「完成」，  
   而不是无限期拖延追求完美。

3. **信任盒子**  
   一旦设定时间盒，执行时不要再纠结  
   「现在做这个对不对」，直接执行。

4. **休息也要装盒**  
   休息不是偷懒，而是恢复精力。  
   在任务之间安排 **5–10 分钟的休息盒**。

5. **大拆小，小合并**  
   - 大任务 → 拆解成小步骤  比如“完成年度报告”这个任务就太大了，你需要把它分解成：收
	集Q1-Q4的业务数据、分析增长趋势、写市场分析部分、制作数据
	图表、撰写总结和建议，等等。
   - 碎事（回微信、整理文件）→ 合并到一个时间盒集中处理

---

##### 4.时间盒为什么时间盒真的有效？

- **对抗帕金森定律**  
  工作会自动膨胀占满所有时间。  
  时间限制倒逼你提高效率，剔除细枝末节。

- **符合帕累托原则（二八法则）**  
  强迫你把精力集中在最重要的 20% 任务上。

- **节省脑力**  
  提前规划，执行时不再消耗脑力做选择，  
  避免决策疲劳。

- **获得掌控感与自由**  
  你不再被事情推着走，  
  而是获得专注于真正重要事情的自由。

- **提升专注力**  
  明确的截止时间能激活大脑前额叶皮层，  
  增强自我控制力。

---
### 三 设计理念与核心决策  
  
**ADHD Timebox Agent**的所有核心设计决策，都是建立在 **时间盒（Timeboxing）管理法的科学原理**上。

对于 ADHD 大脑，单纯要求“罗列任务”往往是无效的。因为 ADHD 的核心挑战正是**难以确立任务的优先级**，面对需要组织与整理的庞杂事务更是一场认知的灾难。

**ADHD Timebox Agent**采用了 **Multi-Agent 协作架构**，由一个中心调度Agent 和三个功能性 Agent 组成。系统通过状态锁机制 管理上下文，确保复杂的多轮对话任务能够完整执行。
#### 1. Orchestrator Agent 

**角色：** 系统的大脑与路由中心。

- **意图识别与分发：** 实时监听用户自然语言输入，分析意图并将任务路由至最合适的 Agent（Plan, Focus 或 Reward）。
	<img width="448" height="118" alt="Screenshot 2026-01-07 at 11 14 06" src="https://github.com/user-attachments/assets/c111bbc4-e0a5-4438-9865-6b2216267745" />

- **Agent Lock (会话锁定机制)：** 当某个 Agent 进入复杂任务流， 如规划任务 时，Orchestrator 会锁定控制权，直到该 Agent 明确发出 `Task Completed` 信号，才会重新接管调度。这确保了任务上下文的连续性，防止逻辑跳跃。

#### 2. Plan Agent

**角色：** 外置的“前额叶皮层”，负责任务的整理、整形与时间管理。

- **清单转时间盒 (List to Timebox)：** 用户只需倾倒碎片化的想法，比如：“今天要写agent代码 学英语 买菜 回邮件 ”，无需提前整理、排序或决策。Plan Agent 会自动分析认知负荷，将其整理并塞入 **15/30/60 分钟** 的时间盒中，将“混乱”转化为可执行的秩序。

- **任务整形 (Task Shaping)：**
    
    - **自动动词化：** 将模糊的名词（如“周报”）转化为清晰的动作（如“撰写周报”）。
    - **拆解与合并：** 自动将大任务拆解为30分钟内的子任务，或将碎片杂事合并，确保难度适中。
  	
 	<img width="450" height="162" alt="Screenshot 2026-01-06 at 23 02 59" src="https://github.com/user-attachments/assets/6d304854-ef1a-4935-98d8-252928788e61" /><br>
	<img width="457" height="184" alt="Screenshot 2026-01-06 at 23 03 11" src="https://github.com/user-attachments/assets/51ccbbcb-0303-435a-8971-99e7002ff9a7" /><br>
    <img width="459" height="328" alt="Screenshot 2026-01-06 at 23 04 23" src="https://github.com/user-attachments/assets/cf0c7faf-3d64-4221-8aa5-337bd9741bb3" /><br>
    <img width="476" height="262" alt="Screenshot 2026-01-06 at 23 04 37" src="https://github.com/user-attachments/assets/f216c966-76bc-4472-8ccd-e3e83c73bcda" /><br>
	<img width="477" height="381" alt="Screenshot 2026-01-07 at 11 15 26" src="https://github.com/user-attachments/assets/b2e19118-e5fb-4931-a80e-1562b876e1b6" /><br>
	
- 会自动把这些日程 同步到 google calendar 里
- **弹性日程 (Dynamic Rescheduling)：** 支持“推迟 30 分钟”等自然语言指令，自动顺延后续计划，防止因一次超时导致整体计划崩塌的挫败感。
  
	<img width="446" height="50" alt="Screenshot 2026-01-07 at 11 21 50" src="https://github.com/user-attachments/assets/bc065b07-1dd1-4d1e-b9f3-210615a60cbe" /><br>
	<img width="446" height="145" alt="Screenshot 2026-01-07 at 11 21 26" src="https://github.com/user-attachments/assets/652aa215-38b5-44ae-abe9-2f989b52ae5b" /><br>
	<img width="444" height="55" alt="Screenshot 2026-01-07 at 11 21 15" src="https://github.com/user-attachments/assets/b783f00a-935e-4938-9545-a52e8caf00ab" /><br>
	<img width="482" height="335" alt="Screenshot 2026-01-06 at 23 13 33" src="https://github.com/user-attachments/assets/b66eeb49-9743-433f-a525-e927d53ab16c" /><br>

#### 3. Focus Agent (执行与守护)

**角色：** 心流守护者，负责对抗拖延与维持注意力。

- **微步启动 (Micro-steps)：** 检测到用户犹豫或拖延时，不进行施压，而是给出极低门槛的建议（如“先打开文档就好”），绕过杏仁核的焦虑反应。
  
   <img width="445" height="424" alt="Screenshot 2026-01-07 at 11 24 07" src="https://github.com/user-attachments/assets/dfca7774-0a85-4a6c-bded-5c97306854d5" />

- **念头停车场 ：** 当用户在执行中产生杂念 如“突然想查新买的一次性胶片机能不能过安检 ”，Agent 会代替用户在后台搜索并存储摘要，让用户无需切换窗口，保护心流的连续性。
  
  <img width="670" height="227" alt="Screenshot 2026-01-07 at 11 31 33" src="https://github.com/user-attachments/assets/8b483a11-65e2-4a7a-b5c1-e348c446cf61" /><br>
  <img width="677" height="235" alt="Screenshot 2026-01-07 at 11 31 51" src="https://github.com/user-attachments/assets/486dfbe0-0043-4f0e-81c7-c179393c9acd" /><br>
  还会保存到 thought_parking 文件中
  
  <img width="563" height="211" alt="Screenshot 2026-01-07 at 11 36 09" src="https://github.com/user-attachments/assets/a0476cca-ba04-4865-85e6-332d37e32f53" /><br>

- **走神检测 (Distraction Detection)：** 实时监测输入设备状态。如果用户超过 5 分钟无鼠标/键盘操作，系统会主动发出温和提醒，拉回注意力。
  
  <img width="663" height="250" alt="Screenshot 2026-01-07 at 11 30 18" src="https://github.com/user-attachments/assets/491868a1-4d4d-45cd-ad17-a8f829b5152b" /><br>

- **状态追踪：** 负责标记当前正在进行的任务及上下文管理。
  
  <img width="587" height="89" alt="Screenshot 2026-01-07 at 11 27 57" src="https://github.com/user-attachments/assets/b29c2d86-78b9-45a1-b569-0e2a1f284169" /><br>

#### 4. Reward Agent (反馈与激励)

**角色：** 多巴胺提供者。

- **即时正反馈：** 当任务被标记为“完成”时，触发即时奖励。
  
  <img width="475" height="314" alt="Screenshot 2026-01-07 at 11 26 22" src="https://github.com/user-attachments/assets/4dfc6806-c0b2-4efb-b1aa-3213c06d559f" /><br>

- **可视化激励：** 生成趣味性的 ASCII Art（如 Cowsay 动物形象）与鼓励语，为枯燥的任务结尾提供成就感与情绪价值。

  <img width="737" height="459" alt="Screenshot 2026-01-07 at 11 25 36" src="https://github.com/user-attachments/assets/d4ee499c-ace1-4c42-889e-4273ca43e5b2" /><br>



### 四 技术挑战与收获
#### 1. 从 "God Prompt" 到 Multi-Agent 架构

- **挑战：** 早期尝试使用单一 Agent 处理所有逻辑包括 规划、监督、奖励，导致 Prompt 过于臃肿。不仅 Token 消耗巨大，且系统极其脆弱——修改一个指令往往会导致其他无关功能的退化，调试难度呈指数级上升。
- 
- **收获：** 采用 **Orchestrator-Worker** 的多智能体协作模式，通过拆分为 `Plan`、`Focus`、`Reward` 三个独立 Agent，实现了模块化开发。现在每个 Agent 仅维护最小必要上下文，既降低了认知负荷，也使得针对性优化 变得安全且高效。
---
#### 2. 从Agent 到 Tools

在系统的早期设计中，我曾陷入“万物皆 Agent”的误区，例如设计了一个独立的 `Parking Agent` 专门负责记录用户的杂念。但在实际运行中，我发现了严重的问题，并最终通过 **Tool Use** 完成了架构重构。

ConnectOnion 的设计哲学——**"Functions are Tools"** 极大地简化了开发。我不需要写复杂的封装类，只需要写标准的 Python 函数，就能直接变成 Agent 可调用的工具。这不仅让我能快速迭代 `Google Calendar`、`System Lock` 等功能，而且还解决了这个痛苦的问题

当用户在专注时说“我想查个资料”，Orchestrator 需要将对话从 `Focus Agent` 切换到 `Parking Agent`。这种设计导致了不必要的上下文切换。
     **路由抖动：** 纯 Prompt 的路由切换往往不稳定，Orchestrator 容易在频繁的切换中丢失原始任务的上下文。
     **体验割裂**  仅仅为了“记个笔记”就切换整个 Agent 人格，不仅消耗 Token，还破坏了用户的心流体验。
    
- **重构时** 我将“念头停车场”降级为 作为 `Focus Agent` 的一个 **Tool**。
用户无需离开当前的专注模式，Agent 只需调用工具即可完成“卸载杂念”，保持了对话的连续性和稳定性。
---
#### 3. 用有限状态机解决 上下文漂移的问题

在开发早期，Orchestrator agent采用的是朴素的无状态路由 模式。这导致了一个严重的上下文漂移问题：
就是当Plan Agent 发起追问 例如：“你想定在几点？”，回复 “九点” 时，Orchestrator 往往因为丢失了上一轮的上下文，无法理解“九点”的含义，甚至错误地将其路由给其他 Agent，导致对话流程断裂，Agent 表现得“呆滞”。

为了解决这个问题，我放弃了依赖 LLM 自身记忆的做法，转而采用了 **“外部状态管理 + 确定性路由”** 的方案。

- LLM 的意图识别是概率性的。当 `Plan Agent` 需要与用户进行多轮交互 比如确认任务细节时，Orchestrator 经常误以为任务已结束，从而过早接管对话，导致逻辑断裂。
- 因此引入了类似 **有限状态机**的锁定机制。
    
    - 当 Agent 调用 `acquire_lock()` 工具时，系统进入 **Sticky Session** 模式。
    
    - Orchestrator 会暂时旁路意图识别逻辑，将后续所有的 User Input **强制路由**给当前持有锁的 Agent，直到其显式调用 `release_lock()`。这确保了Workflow 的原子性和完整性。

---

#### 4.Agent 的“重启失忆”问题

Plan Agent 缺乏“状态持久化感知”。尽管代码已经将用户的计划保存为 `daily_tasks.json` 文件，但每当程序重启或开始新会话时，Agent 表现得像第一次启动一样，完全不知道已有计划的存在。

**根本原因 (Root Cause)：**

- **LLM 的无状态性 (Statelessness)：** LLM 本身不具备长时记忆，只依赖当前的 `Context Window`（上下文窗口）。
    
- **上下文断层：** 虽然数据在磁盘上（持久化层），但在 Agent 初始化时，没有将这些数据加载回内存（应用层）并注入到 Prompt 中。Agent 和磁盘文件之间隔了一堵墙。
    
为了解决这个问题，我引入了一个架构层的中间件——**State Manager**，将“记忆的维护”从 Agent 的推理逻辑中剥离出来，交给确定性的代码处理。

状态注水  不再依赖 Agent 主动去“查”文件，而是采用**主动注入**策略：

我将 LLM 视为**无状态 (Stateless)** 的推理引擎。在每一轮对话发起前，代码层会先从后端读取最新的 `System State`（如当前时间、任务列表、剩余时间），将其组装成 Prompt **动态注入** 到当次请求中。

这样无论对话进行了多久，Agent 在每一轮都能看到“最新鲜、最客观”的世界状态，彻底根除了因记忆衰减导致的逻辑漂移。



#### 5. 引入 Memory 让agent 拥有长期记忆

在引入 ConnectOnion 的 `Memory` 模块之前， **ADHD Timebox Agent** 通过 daily_tasks.json 和 上下文注 实现了状态持久化。它精确地记得“现在是 14:00，你在做任务 B，进度 50%”。哪怕重启，它读取 JSON 也能立刻恢复状态。
也能知道现在的任务是什么。但它的局限在于：它只能记住“设计好”的字段，比如 : start_time、end_time、status、title。但如果用户说了一句：“我发现我下午 2 点特别容易困，以后这个时间别排重活”。旧系统会因找不到 user_energy_pattern 这种字段，只能把这句话当做闲聊处理，或者存进 thought_parking 仅仅是个备忘录 别的agent 不会读 ，而在下次 Plan agent 排期时，依然会在下午 2 点排重活。

加入 Memory 后，拥有了“非结构化认知” 像一个贴身管家。它不仅看表格，还会拿个小本本记下用户的“脾气”和“习惯”。

- 旧系统：Plan Agent把任务扔给 Focus 就不管了。

- 新系统：Plan Agent 可以在 Memory 里留个便条——focus_note: "这个用户最近压力大，执行阶段多鼓励，少催促"。Focus Agent 虽然没参与排期，但看到这个便条，对你的语气就会变温柔。它让系统能从过去的互动中学习，产生那些 JSON 字段里装不下的“默契”和“直觉”。 

  <img width="548" height="89" alt="Screenshot 2026-01-07 at 11 34 40" src="https://github.com/user-attachments/assets/17710038-4e6d-4e35-9f41-8f3ebe6cadc5" /><br>
  <img width="536" height="98" alt="Screenshot 2026-01-07 at 11 34 30" src="https://github.com/user-attachments/assets/34ba26a8-e3d8-446b-ba38-d5c4dbea171d" /><br>
  <img width="537" height="43" alt="Screenshot 2026-01-07 at 11 34 17" src="https://github.com/user-attachments/assets/8bfb6814-2f76-4f81-ba0c-774623e5e87e" /><br>

### 五、总结与致谢

ADHD Timebox Agent 利用 ConnectOnion 强大的 Memory 能力和灵活的 Multi-Agent 编排，成功将一个“只会看日程表的机械程序”，升级成了一个“有记忆、懂默契、能进化”的聪明Agent。
感谢 ConnectOnion，让复杂的事情变得简单，让 AI 成为了我大脑的延伸。
