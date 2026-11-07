"""Fixture content for offline demo mode (the two demonstration topics).

Claims reference sources by placeholder (e.g. ``@rfc9110``) and are resolved to
real source IDs from the evidence pack at run time. Evidence excerpts are
verbatim sentences from the captured documentation text, so the deterministic
quote verifier checks them exactly as it would live data. One claim per lesson
is deliberately left without a source so the traceability features have an
honest "Unsupported" case to show.
"""
from __future__ import annotations

SOURCE_PLACEHOLDERS = {
    "@rfc9110": "rfc-editor.org/rfc/rfc9110",
    "@mdn_get": "Methods/GET",
    "@mdn_post": "Methods/POST",
    "@mdn_idem": "Glossary/Idempotent",
    "@mdn_status": "Reference/Status",
    "@pg": "postgresql.org",
    "@ms": "learn.microsoft.com",
}

ANALYSIS = {
    "http": {
        "interpretation": "Learners must be able to explain what GET and POST requests do, using the HTTP "
                          "semantics of safety and idempotency, and classify a response by its status-code class "
                          "(2xx success, 4xx client error, 5xx server error).",
        "learners_should_understand": [
            "HTTP is a request/response protocol: a client sends a method and target, the server returns a status code",
            "GET retrieves a representation and is safe and idempotent",
            "POST asks the target resource to process enclosed data and is neither safe nor idempotent",
            "The first digit of a status code identifies its class",
        ],
        "learners_should_be_able_to": [
            "Choose GET or POST for a described interaction and justify the choice",
            "Classify a given status code as 2xx, 4xx or 5xx and say who must act",
        ],
        "key_concepts": ["HTTP request and response", "GET method", "POST method", "safe methods",
                         "idempotent methods", "status code classes", "2xx successful", "4xx client error",
                         "5xx server error"],
        "expected_difficulty": "Beginners often confuse 'safe' with 'secure' and assume a 4xx/5xx always means "
                               "a bug in their own code.",
        "prerequisites": ["What a web browser and a web server are", "What a URL is"],
        "assessment_methods": ["Multiple-choice classification of status codes",
                               "Short scenario questions choosing GET vs POST"],
        "learning_outcomes": [
            {"id": "LO1", "outcome": "Explain the purpose of the GET method and why it is safe and idempotent",
             "bloom_level": "Understand", "measurable_by": "Short-answer explanation"},
            {"id": "LO2", "outcome": "Explain the purpose of the POST method and why repeating it can have additional effects",
             "bloom_level": "Understand", "measurable_by": "Scenario question"},
            {"id": "LO3", "outcome": "Distinguish 2xx, 4xx and 5xx status codes and identify the responsible party",
             "bloom_level": "Analyze", "measurable_by": "Classification questions"},
        ],
        "search_queries": ["RFC 9110 HTTP semantics safe idempotent methods", "MDN HTTP GET method",
                           "MDN HTTP POST method", "HTTP response status codes classes 2xx 4xx 5xx"],
    },
    "sql": {
        "interpretation": "Learners must explain how INNER, LEFT, RIGHT and FULL OUTER joins decide which rows "
                          "appear in the result, and demonstrate each on two small related tables.",
        "learners_should_understand": [
            "A join condition decides which pairs of rows match",
            "INNER JOIN keeps only matching pairs",
            "Outer joins keep unmatched rows and fill the missing side with NULL",
        ],
        "learners_should_be_able_to": [
            "Write each of the four joins for two tables",
            "Predict the rows (including NULLs) each join returns",
        ],
        "key_concepts": ["join condition", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL OUTER JOIN",
                         "NULL in outer joins", "foreign key"],
        "expected_difficulty": "Learners struggle to predict NULL-filled rows and to remember which table is "
                               "'left' in a query.",
        "prerequisites": ["Basic SELECT ... FROM ... WHERE", "What a primary key and foreign key are"],
        "assessment_methods": ["Predict-the-output questions", "Write-the-query practical task"],
        "learning_outcomes": [
            {"id": "LO1", "outcome": "Explain how INNER JOIN selects rows using the join condition",
             "bloom_level": "Understand", "measurable_by": "Short-answer question"},
            {"id": "LO2", "outcome": "Explain how LEFT, RIGHT and FULL OUTER JOIN preserve unmatched rows with NULLs",
             "bloom_level": "Understand", "measurable_by": "Multiple-choice question"},
            {"id": "LO3", "outcome": "Write and predict the result of each join on two related tables",
             "bloom_level": "Apply", "measurable_by": "Practical query-writing task"},
        ],
        "search_queries": ["PostgreSQL documentation joined tables LEFT OUTER JOIN",
                           "SQL Server joins documentation", "SQL INNER JOIN LEFT JOIN RIGHT JOIN FULL OUTER JOIN"],
    },
}

HTTP_LESSON = {
    "title": "HTTP Requests and Responses",
    "learning_objective": "",
    "learning_outcomes": [o["outcome"] for o in ANALYSIS["http"]["learning_outcomes"]],
    "target_audience": "Beginners starting web development or API work",
    "assumed_knowledge": "You have used a web browser and know what a URL looks like. No programming is required.",
    "sections": [
        {"id": "intro", "kind": "introduction", "title": "Why every click is a conversation", "duration_minutes": 4,
         "activity": "Read the scenario and predict what the browser sends.",
         "content": "Every time you open a page, submit a form or an app refreshes your feed, a **client** sends an HTTP "
                    "**request** and a **server** answers with a **response**. Two questions decide most of what "
                    "happens: *which method* did the client use, and *which status code* came back?\n\n"
                    "In this lesson you will learn the two most common methods, **GET** and **POST**, and how to read "
                    "the three status-code classes you will meet daily: **2xx**, **4xx** and **5xx**."},
        {"id": "prereq", "kind": "prerequisites", "title": "Anatomy of a request and a response", "duration_minutes": 3,
         "activity": "Label the parts of the sample messages.",
         "content": "```http\nGET /books/42 HTTP/1.1\nHost: library.example\n```\n\n```http\nHTTP/1.1 200 OK\n"
                    "Content-Type: application/json\n\n{\"id\": 42, \"title\": \"Dune\"}\n```\n\n"
                    "A request starts with a **method** and a **target**; a response starts with a three-digit "
                    "**status code**."},
        {"id": "get", "kind": "concept", "title": "GET: asking for a representation", "duration_minutes": 6,
         "activity": "Read, then explain 'safe' and 'idempotent' in your own words.",
         "content": "GET asks the server to transfer a representation of the target resource [C1]. It is the "
                    "workhorse of the web: loading pages, images and API data.\n\nGET is **safe**: its meaning is "
                    "essentially read-only, so the client is not asking the server to change anything [C2]. GET, "
                    "HEAD, OPTIONS and TRACE are the safe methods defined by HTTP [C3].\n\nGET is also "
                    "**idempotent**: sending the same request many times has the same *intended* effect as sending "
                    "it once [C4]. That is why clients can retry it automatically after a network failure [C5].\n\n"
                    "> \"Safe\" is about intended effect, not security. A GET can still be logged by the server."},
        {"id": "post", "kind": "concept", "title": "POST: asking the server to process data", "duration_minutes": 6,
         "activity": "Compare GET and POST using the table.",
         "content": "POST asks the target resource to process the data enclosed in the request according to its own "
                    "rules [C6] — submitting a form, placing an order, uploading a comment.\n\nPOST is **neither safe "
                    "nor idempotent**. Repeating an identical POST may have additional effects, such as creating "
                    "the same order twice [C7]. When a POST creates something, the server should answer "
                    "**201 Created** with a Location header [C8]. This is also why browsers usually warn before "
                    "re-submitting a form when you refresh the page [C9].\n\n"
                    "| | GET | POST |\n|---|---|---|\n| Purpose | Retrieve a representation | Process enclosed data |\n"
                    "| Safe | Yes | No |\n| Idempotent | Yes | No (not guaranteed) |\n| Has request body | No (undefined) | Yes |"},
        {"id": "status", "kind": "concept", "title": "Reading status codes by their first digit", "duration_minutes": 6,
         "activity": "Sort the example codes into the three classes.",
         "content": "The first digit of a status code tells you its class [C10]:\n\n"
                    "| Class | Meaning | Who should act? | Examples |\n|---|---|---|---|\n"
                    "| 2xx | The request was received, understood and accepted [C11] | Nobody — it worked | 200 OK, 201 Created, 204 No Content |\n"
                    "| 4xx | The client seems to have erred [C12] | The client: fix the request | 400 Bad Request, 401 Unauthorized, 404 Not Found |\n"
                    "| 5xx | The server erred or cannot perform the request [C13] | The server operator | 500 Internal Server Error, 503 Service Unavailable |\n\n"
                    "Even an unfamiliar code can be interpreted from its first digit."},
        {"id": "worked", "kind": "worked_example", "title": "Worked example: a small library API", "duration_minutes": 6,
         "activity": "Follow each step and predict the status code before reading it.",
         "content": "**Step 1 — read a book.**\n\n```http\nGET /books/42 HTTP/1.1\nHost: library.example\n```\n"
                    "Response: `200 OK` with the book's JSON. Safe and idempotent: refreshing is harmless.\n\n"
                    "**Step 2 — add a review.**\n\n```http\nPOST /books/42/reviews HTTP/1.1\nHost: library.example\n"
                    "Content-Type: application/json\n\n{\"stars\": 5, \"text\": \"Loved it\"}\n```\n"
                    "Response: `201 Created` with `Location: /books/42/reviews/7`. Sending it twice could create two reviews.\n\n"
                    "**Step 3 — a typo in the URL.** `GET /bokks/42` → `404 Not Found` (4xx: fix the request).\n\n"
                    "**Step 4 — the database is down.** `GET /books/42` → `503 Service Unavailable` (5xx: not your fault; retry later)."},
        {"id": "apps", "kind": "application", "title": "Where you will meet this", "duration_minutes": 3,
         "activity": "Discuss which method each everyday action uses.",
         "content": "- **Search boxes** usually use GET so results can be bookmarked and shared.\n"
                    "- **Checkout and login forms** use POST because they submit data that changes state.\n"
                    "- **Monitoring dashboards** alert on spikes of 5xx responses; a rise in 4xx often points to a "
                    "broken client release."},
        {"id": "activity", "kind": "activity", "title": "Activity: method and status detective", "duration_minutes": 6,
         "activity": "Complete the table individually, then compare with a partner or the answer key.",
         "content": "For each scenario write (a) the method you would use and (b) the most likely status-code class.\n\n"
                    "1. Loading a product page that exists.\n2. Submitting a sign-up form successfully.\n"
                    "3. Requesting `/users/999` where user 999 does not exist.\n"
                    "4. Uploading a photo while the server crashes.\n5. Refreshing a search results page.\n\n"
                    "**Expected:** 1 GET/2xx · 2 POST/2xx (201) · 3 GET/4xx (404) · 4 POST/5xx · 5 GET/2xx."},
        {"id": "check", "kind": "knowledge_check", "title": "Knowledge check", "duration_minutes": 5,
         "activity": "Answer without notes.", "content": "Answer the questions below."},
        {"id": "answers", "kind": "answers", "title": "Answers and explanations", "duration_minutes": 2,
         "activity": "Mark your answers and read each explanation.", "content": "Check your reasoning, not just the letter."},
        {"id": "takeaways", "kind": "takeaways", "title": "Key takeaways", "duration_minutes": 1,
         "activity": "Read and highlight.",
         "content": "- GET retrieves; it is safe and idempotent.\n- POST asks the server to process data; repeats can add effects.\n"
                    "- 2xx = success, 4xx = client error, 5xx = server error."},
        {"id": "summary", "kind": "summary", "title": "Summary", "duration_minutes": 2,
         "activity": "Write one sentence summarising the lesson.",
         "content": "HTTP is a conversation of methods and status codes. Pick GET to read and POST to submit, and read "
                    "the first digit of any status code to know whether it worked, whether the request needs fixing, "
                    "or whether the server is at fault."},
    ],
    "knowledge_check": [
        {"id": "Q1", "question": "Why can a client safely retry a GET request after a network timeout?",
         "kind": "short_answer", "options": [],
         "answer": "Because GET is idempotent: repeating it has the same intended effect as sending it once.",
         "explanation": "Idempotency is about the intended effect on the server; retrying cannot create extra changes.",
         "outcome_ids": ["LO1"]},
        {"id": "Q2", "question": "A user double-clicks 'Place order' and two identical POST requests are sent. What can happen?",
         "kind": "multiple_choice",
         "options": ["Nothing, POST is idempotent", "Two orders may be created", "The server must return 404", "The browser converts it to GET"],
         "answer": "Two orders may be created",
         "explanation": "POST is not idempotent, so identical requests may each have an effect.", "outcome_ids": ["LO2"]},
        {"id": "Q3", "question": "Which status code class indicates that the client's request was malformed or cannot be fulfilled?",
         "kind": "multiple_choice", "options": ["2xx", "3xx", "4xx", "5xx"], "answer": "4xx",
         "explanation": "4xx codes signal client errors such as 400 or 404.", "outcome_ids": ["LO3"]},
        {"id": "Q4", "question": "Your API returns 503 during a database outage. Who needs to act?",
         "kind": "multiple_choice", "options": ["The client", "The server operator", "Nobody", "The DNS provider"],
         "answer": "The server operator",
         "explanation": "5xx codes mean the server failed to fulfil an apparently valid request.", "outcome_ids": ["LO3"]},
        {"id": "Q5", "question": "Which method should a search form use if results must be bookmarkable, and why?",
         "kind": "short_answer", "options": [],
         "answer": "GET, because it only retrieves data and its parameters live in the URL.",
         "explanation": "Searching does not change server state, so the safe GET method fits.", "outcome_ids": ["LO1", "LO2"]},
    ],
    "claims": [
        {"id": "C1", "text": "GET requests transfer of a current selected representation for the target resource.",
         "section_id": "get", "source_ids": ["@rfc9110"],
         "evidence_excerpt": "The GET method requests transfer of a current selected representation for the target resource."},
        {"id": "C2", "text": "Safe methods have essentially read-only semantics.", "section_id": "get",
         "source_ids": ["@rfc9110"],
         "evidence_excerpt": "Request methods are considered safe if their defined semantics are essentially read-only"},
        {"id": "C3", "text": "GET, HEAD, OPTIONS and TRACE are defined to be safe.", "section_id": "get",
         "source_ids": ["@rfc9110"],
         "evidence_excerpt": "Of the request methods defined by this specification, the GET, HEAD, OPTIONS, and TRACE methods are defined to be safe."},
        {"id": "C4", "text": "Safe methods, including GET, are idempotent.", "section_id": "get",
         "source_ids": ["@rfc9110"],
         "evidence_excerpt": "Of the request methods defined by this specification, PUT, DELETE, and safe request methods are idempotent."},
        {"id": "C5", "text": "Requests using idempotent methods can be retried safely.", "section_id": "get",
         "source_ids": ["@mdn_idem"],
         "evidence_excerpt": "A client can safely retry a request that uses an idempotent method"},
        {"id": "C6", "text": "POST asks the target resource to process the enclosed representation according to its own semantics.",
         "section_id": "post", "source_ids": ["@rfc9110"],
         "evidence_excerpt": "The POST method requests that the target resource process the representation enclosed in the request according to the resource's own specific semantics."},
        {"id": "C7", "text": "Repeating identical POST requests may have additional effects such as duplicate orders.",
         "section_id": "post", "source_ids": ["@mdn_post"],
         "evidence_excerpt": "Successive identical POST requests may have additional effects, such as creating the same order several times."},
        {"id": "C8", "text": "When POST creates a resource the server should respond 201 Created with a Location header.",
         "section_id": "post", "source_ids": ["@rfc9110"],
         "evidence_excerpt": "the origin server SHOULD send a 201 (Created) response containing a Location header field"},
        {"id": "C9", "text": "Browsers usually warn before re-submitting a POST form when the page is refreshed.",
         "section_id": "post", "source_ids": [], "evidence_excerpt": None},
        {"id": "C10", "text": "The first digit of a status code defines its class.", "section_id": "status",
         "source_ids": ["@rfc9110"], "evidence_excerpt": "The first digit of the status code defines the class of response."},
        {"id": "C11", "text": "2xx means the request was successfully received, understood and accepted.",
         "section_id": "status", "source_ids": ["@rfc9110"],
         "evidence_excerpt": "The 2xx (Successful) class of status code indicates that the client's request was successfully received, understood, and accepted."},
        {"id": "C12", "text": "4xx means the client seems to have erred.", "section_id": "status",
         "source_ids": ["@rfc9110"],
         "evidence_excerpt": "The 4xx (Client Error) class of status code indicates that the client seems to have erred."},
        {"id": "C13", "text": "5xx means the server erred or cannot perform the requested method.",
         "section_id": "status", "source_ids": ["@rfc9110", "@mdn_status"],
         "evidence_excerpt": "The 5xx (Server Error) class of status code indicates that the server is aware that it has erred or is incapable of performing the requested method."},
    ],
}

SQL_TABLES = (
    "**customers**\n\n| customer_id | name | city |\n|---|---|---|\n| 1 | Asha | Pune |\n| 2 | Ben | Leeds |\n| 3 | Chen | Austin |\n\n"
    "**orders**\n\n| order_id | customer_id | amount |\n|---|---|---|\n| 101 | 1 | 250 |\n| 102 | 1 | 75 |\n| 103 | 3 | 120 |\n| 104 | 4 | 60 |\n\n"
    "Ben (2) has no orders. Order 104 belongs to customer 4, who is not in `customers`."
)

SQL_LESSON = {
    "title": "Introduction to SQL Joins",
    "learning_objective": "",
    "learning_outcomes": [o["outcome"] for o in ANALYSIS["sql"]["learning_outcomes"]],
    "target_audience": "Beginners who can write simple SELECT queries",
    "assumed_knowledge": "SELECT, FROM and WHERE; the idea of primary and foreign keys.",
    "sections": [
        {"id": "intro", "kind": "introduction", "title": "Why data lives in more than one table", "duration_minutes": 3,
         "activity": "Think of a question that needs data from two tables.",
         "content": "Real databases split data into related tables: customers in one, orders in another. A **join** "
                    "combines rows from two tables based on a logical relationship between them [C1], typically a "
                    "foreign key in one table matched to a key in the other [C2]."},
        {"id": "tables", "kind": "prerequisites", "title": "Our two sample tables", "duration_minutes": 3,
         "activity": "Study the tables; note the unmatched rows.", "content": SQL_TABLES},
        {"id": "inner", "kind": "concept", "title": "INNER JOIN: only the matches", "duration_minutes": 5,
         "activity": "Trace which pairs satisfy the condition.",
         "content": "For each row of the left table, an inner join produces a row for every row of the right table "
                    "that satisfies the join condition [C3]. A pair matches when the `ON` expression is true [C4]. "
                    "Unmatched rows on either side disappear. The keyword `INNER` is optional: `JOIN` alone means "
                    "an inner join [C5]."},
        {"id": "outer", "kind": "concept", "title": "LEFT, RIGHT and FULL OUTER JOIN: keeping the unmatched", "duration_minutes": 7,
         "activity": "Fill the comparison table from memory after reading.",
         "content": "Outer joins start with the inner join and then add back unmatched rows, filling the other side "
                    "with `NULL`.\n\n- **LEFT JOIN** keeps every row of the left table at least once [C6].\n"
                    "- **RIGHT JOIN** is the converse: every row of the right table appears [C7].\n"
                    "- **FULL OUTER JOIN** adds unmatched rows from both sides [C8].\n\n"
                    "| Join | Unmatched left rows | Unmatched right rows |\n|---|---|---|\n"
                    "| INNER | dropped | dropped |\n| LEFT | kept (right side NULL) | dropped |\n"
                    "| RIGHT | dropped | kept (left side NULL) |\n| FULL OUTER | kept | kept |\n\n"
                    "Note: MySQL does not provide FULL OUTER JOIN directly; it is usually emulated with a UNION of a "
                    "LEFT and a RIGHT join [C9]."},
        {"id": "worked", "kind": "worked_example", "title": "Worked examples with expected results", "duration_minutes": 7,
         "activity": "Predict each result before reading it.",
         "content": "```sql\nSELECT c.name, o.order_id\nFROM customers c\nINNER JOIN orders o ON c.customer_id = o.customer_id;\n```\n\n"
                    "| name | order_id |\n|---|---|\n| Asha | 101 |\n| Asha | 102 |\n| Chen | 103 |\n\n"
                    "```sql\nSELECT c.name, o.order_id\nFROM customers c\nLEFT JOIN orders o ON c.customer_id = o.customer_id;\n```\n\n"
                    "| name | order_id |\n|---|---|\n| Asha | 101 |\n| Asha | 102 |\n| Ben | NULL |\n| Chen | 103 |\n\n"
                    "```sql\nSELECT c.name, o.order_id\nFROM customers c\nRIGHT JOIN orders o ON c.customer_id = o.customer_id;\n```\n\n"
                    "| name | order_id |\n|---|---|\n| Asha | 101 |\n| Asha | 102 |\n| Chen | 103 |\n| NULL | 104 |\n\n"
                    "```sql\nSELECT c.name, o.order_id\nFROM customers c\nFULL OUTER JOIN orders o ON c.customer_id = o.customer_id;\n```\n\n"
                    "| name | order_id |\n|---|---|\n| Asha | 101 |\n| Asha | 102 |\n| Ben | NULL |\n| Chen | 103 |\n| NULL | 104 |\n\n"
                    "Row counts: INNER 3, LEFT 4, RIGHT 4, FULL 5. Row order may differ without `ORDER BY`."},
        {"id": "apps", "kind": "application", "title": "Joins in real work", "duration_minutes": 3,
         "activity": "Match each business question to a join type.",
         "content": "- *Which customers have never ordered?* LEFT JOIN, then `WHERE o.order_id IS NULL`.\n"
                    "- *Which orders reference a missing customer?* RIGHT (or LEFT from orders) JOIN, filter NULL names.\n"
                    "- *Reconcile two systems' records:* FULL OUTER JOIN shows rows missing on either side."},
        {"id": "activity", "kind": "activity", "title": "Activity: write and predict", "duration_minutes": 7,
         "activity": "Write the queries in any SQL sandbox (e.g. SQLite 3.39+ or PostgreSQL) and check the counts.",
         "content": "1. Write a query listing every customer and the total amount they ordered (0 or NULL for none).\n"
                    "2. Write a query that finds orders whose customer does not exist.\n"
                    "3. Predict how many rows a FULL OUTER JOIN returns if Ben places order 105.\n\n"
                    "**Expected:** 1 uses LEFT JOIN + GROUP BY (3 rows: Asha 325, Ben NULL, Chen 120) · "
                    "2 returns order 104 · 3 returns 5 rows (Ben now matches)."},
        {"id": "check", "kind": "knowledge_check", "title": "Knowledge check", "duration_minutes": 4,
         "activity": "Answer without running queries.", "content": "Use the sample tables."},
        {"id": "answers", "kind": "answers", "title": "Answers and explanations", "duration_minutes": 2,
         "activity": "Compare your reasoning.", "content": "Each answer explains which rows are kept or dropped."},
        {"id": "takeaways", "kind": "takeaways", "title": "Key takeaways", "duration_minutes": 1,
         "activity": "Read.",
         "content": "- INNER keeps matches only.\n- LEFT keeps all left rows; RIGHT keeps all right rows.\n"
                    "- FULL OUTER keeps everything; missing sides become NULL."},
        {"id": "summary", "kind": "summary", "title": "Summary", "duration_minutes": 2,
         "activity": "Explain the four joins to a partner in one minute.",
         "content": "Every join starts from the matching pairs. Outer joins then add back unmatched rows from the left, "
                    "the right, or both, filling the gaps with NULL."},
    ],
    "knowledge_check": [
        {"id": "Q1", "question": "How many rows does the INNER JOIN of customers and orders return, and why is Ben missing?",
         "kind": "short_answer", "options": [], "answer": "3 rows; Ben has no matching order.",
         "explanation": "An inner join keeps only pairs that satisfy the join condition.", "outcome_ids": ["LO1"]},
        {"id": "Q2", "question": "Which join returns Ben with a NULL order_id but not order 104?",
         "kind": "multiple_choice", "options": ["INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL OUTER JOIN"],
         "answer": "LEFT JOIN",
         "explanation": "LEFT keeps every customer (left table) but drops unmatched orders.", "outcome_ids": ["LO2"]},
        {"id": "Q3", "question": "What value fills the customer columns for order 104 in a RIGHT JOIN?",
         "kind": "multiple_choice", "options": ["0", "An empty string", "NULL", "The row is removed"],
         "answer": "NULL", "explanation": "Outer joins fill the missing side with NULL.", "outcome_ids": ["LO2"]},
        {"id": "Q4", "question": "Write a query that lists customers who have never placed an order.",
         "kind": "practical", "options": [],
         "answer": "SELECT c.name FROM customers c LEFT JOIN orders o ON c.customer_id = o.customer_id WHERE o.order_id IS NULL;",
         "explanation": "LEFT JOIN keeps Ben with NULL order columns; filtering on IS NULL isolates him.",
         "outcome_ids": ["LO3"]},
        {"id": "Q5", "question": "How many rows does FULL OUTER JOIN return on the sample tables?",
         "kind": "multiple_choice", "options": ["3", "4", "5", "12"], "answer": "5",
         "explanation": "3 matches + Ben (unmatched left) + order 104 (unmatched right).", "outcome_ids": ["LO2", "LO3"]},
    ],
    "claims": [
        {"id": "C1", "text": "Joins retrieve data from two or more tables based on logical relationships between them.",
         "section_id": "intro", "source_ids": ["@ms"],
         "evidence_excerpt": "By using joins, you can retrieve data from two or more tables based on logical relationships between the tables."},
        {"id": "C2", "text": "A typical join condition matches a foreign key in one table to its associated key in the other.",
         "section_id": "intro", "source_ids": ["@ms"],
         "evidence_excerpt": "A typical join condition specifies a foreign key from one table and its associated key in the other table."},
        {"id": "C3", "text": "An inner join produces a row for each pair of rows that satisfies the join condition.",
         "section_id": "inner", "source_ids": ["@pg"],
         "evidence_excerpt": "For each row R1 of T1, the joined table has a row for each row in T2 that satisfies the join condition with R1."},
        {"id": "C4", "text": "Two rows match when the ON expression evaluates to true.", "section_id": "inner",
         "source_ids": ["@pg"], "evidence_excerpt": "A pair of rows from T1 and T2 match if the ON expression evaluates to true."},
        {"id": "C5", "text": "INNER is the default join type; the words INNER and OUTER are optional.", "section_id": "inner",
         "source_ids": ["@pg"], "evidence_excerpt": "The words INNER and OUTER are optional in all forms. INNER is the default"},
        {"id": "C6", "text": "A left join always has at least one row for each row of the left table.", "section_id": "outer",
         "source_ids": ["@pg"], "evidence_excerpt": "Thus, the joined table always has at least one row for each row in T1."},
        {"id": "C7", "text": "A right join is the converse of a left join and keeps every row of the right table.",
         "section_id": "outer", "source_ids": ["@pg"],
         "evidence_excerpt": "This is the converse of a left join: the result table will always have a row for each row in T2."},
        {"id": "C8", "text": "A full outer join adds unmatched rows from both tables with NULLs for the missing side.",
         "section_id": "outer", "source_ids": ["@pg"],
         "evidence_excerpt": "Also, for each row of T2 that does not satisfy the join condition with any row in T1, a joined row with null values in the columns of T1 is added."},
        {"id": "C9", "text": "MySQL does not support FULL OUTER JOIN directly; it is emulated with UNION.", "section_id": "outer",
         "source_ids": [], "evidence_excerpt": None},
    ],
}

LESSONS = {"http": HTTP_LESSON, "sql": SQL_LESSON}

# Facts a correct lesson on each topic must state; checked by the demo
# stand-in evaluator against the actual lesson text (regex, case-insensitive).
KEY_FACTS = {
    "http": [
        ("GET is described as safe", r"get[^.]*\bsafe\b|\bsafe\b[^.]*\bget\b"),
        ("GET is described as idempotent", r"get[^.]*idempotent|idempotent[^.]*\bget\b"),
        ("POST is described as not idempotent", r"post[^.]*(not|neither)[^.]*idempotent"),
        ("2xx described as success", r"2xx[^\n]*(success|accepted)"),
        ("4xx described as client error", r"4xx[^\n]*client"),
        ("5xx described as server error", r"5xx[^\n]*server"),
    ],
    "sql": [
        ("INNER JOIN keeps only matching rows", r"inner[^.]*(match|satisf)"),
        ("LEFT JOIN keeps all left rows", r"left join[^.]*(every|all|at least one)"),
        ("RIGHT JOIN keeps all right rows", r"right join[^.]*(every|all|converse)"),
        ("FULL OUTER JOIN keeps unmatched rows from both", r"full outer join[^.]*(both|everything)"),
        ("Outer joins fill missing columns with NULL", r"null"),
    ],
}
