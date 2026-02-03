# Smart Assistant Validation Checklist

## Overview

This document outlines test cases and validation steps for the Sentinel Security Assistant.

**Sentinel is NOT a generic chatbot.** It behaves like a junior SOC analyst sitting on the user's machine.

---

## Core Behavior Rules to Validate

### 1. Context Awareness
- [ ] Follow-up questions ("that", "this", "it", "more") refer to recent topic
- [ ] Never asks user to restate context

### 2. Local-First (Offline)
- [ ] All responses work offline
- [ ] Never suggests cloud services
- [ ] All data from local sources (Event Viewer, Defender, Firewall, KB)
- [ ] Never says "I need internet to answer"

### 3. Hybrid Deterministic + AI
- [ ] KB lookups come first (deterministic)
- [ ] AI enhances but never overrides facts
- [ ] Sources clearly show what data was used

### 4. Error Handling
- [ ] NEVER shows raw errors, stack traces, or code messages
- [ ] Errors explained calmly in human language
- [ ] Clarifies errors do NOT indicate danger
- [ ] Provides safe inference and next step

### 5. Permission Issues
- [ ] States clearly it's a PERMISSION issue
- [ ] Never implies protection is disabled
- [ ] Infers risk from available evidence

---

## Risk Scoring System Validation

### Risk Score Range (0-100)

| Score Range | Classification | Verdict | Test Case |
|-------------|---------------|---------|-----------|
| 0-10 | Normal | Clean | Ask about Event 4624 (logon) |
| 11-30 | Benign | Clean | Ask about Event 7036 (service change) |
| 31-60 | Suspicious | Suspicious | Ask about Event 4625 (failed logon) |
| 61-100 | High Risk | Likely Malicious | Ask about Event 4688 with unusual parent |

### Validation Steps

- [ ] Risk score badge shows in UI (🛡️ X/100)
- [ ] Verdict badge shows (Clean/Suspicious/Likely Malicious)
- [ ] Color coding correct (Green/Blue/Orange/Red)
- [ ] "Show details" reveals full risk analysis
- [ ] "Why Safe" explanation present
- [ ] "What Would Make It Risky" explanation present
- [ ] Detection score (0-70) visible in details

### Security Status Risk Scoring

| Scenario | Expected Score | Classification |
|----------|---------------|----------------|
| All enabled | 0 | Normal / Clean |
| Defender RTP off | 20+ | Suspicious |
| Firewall disabled | 30+ | Suspicious |
| Both off | 60+ | High Risk |

---

## 1. Conversation Memory & Follow-up Handling

### Test Cases

| # | User Message | Expected Behavior |
|---|-------------|------------------|
| 1 | "What's my security status?" | Full security status response with Defender + Firewall info |
| 2 | "Tell me more about it" | Follow-up should reference previous security status context |
| 3 | "Is Windows Defender enabled?" | Defender-specific response |
| 4 | "What about malware protection?" | Should understand context is still about Defender |
| 5 | "Now check my firewall" | Should switch topic to firewall, clear previous topic |
| 6 | "Is it blocking threats?" | Should understand "it" refers to firewall |

### Validation Steps

- [ ] Send message #1, verify full response
- [ ] Send message #2 immediately after, verify it references security status
- [ ] Clear chat, verify memory is cleared
- [ ] Start new conversation, verify no old context leaks

### Memory Limits

- [ ] Send 20+ messages, verify only last 15 are retained
- [ ] Verify old messages are properly forgotten

---

## 2. Intent Classification Accuracy

### Test Cases

| Message | Expected Intent |
|---------|----------------|
| "Hello" | GREETING |
| "Hi there!" | GREETING |
| "What can you do?" | APP_HELP |
| "How do I scan a file?" | APP_HELP |
| "What is event 4624?" | EVENT_EXPLAIN |
| "Explain logon event" | EVENT_EXPLAIN |
| "Is my system secure?" | SECURITY_STATUS |
| "Check my security" | SECURITY_STATUS |
| "Is Windows Defender on?" | DEFENDER_STATUS |
| "Defender status?" | DEFENDER_STATUS |
| "Is my firewall enabled?" | FIREWALL_STATUS |
| "Check firewall" | FIREWALL_STATUS |
| "How do I stay safe online?" | GENERAL_SECURITY_QA |
| "What is phishing?" | GENERAL_SECURITY_QA |
| "Yes" | FOLLOWUP |
| "Tell me more" | FOLLOWUP |

### Validation Steps

- [ ] Test each message above
- [ ] Verify intent is correctly classified (check console logs)
- [ ] Verify appropriate response type is generated

---

## 3. No UI Freeze During AI Processing

### Test Cases

| Scenario | Expected Behavior |
|----------|------------------|
| Send complex query | UI remains responsive, thinking indicator shows |
| Send multiple rapid queries | Only first is processed, subsequent are queued or ignored |
| Query requiring PowerShell call | UI doesn't freeze during subprocess execution |

### Validation Steps

- [ ] Send "What's my security status?" and immediately try scrolling the chat
- [ ] Verify thinking indicator animates smoothly
- [ ] Verify chat scroll remains responsive
- [ ] Time response - should complete within 2-3 seconds

---

## 4. Deterministic Event Explanations

### Test Cases

| Event ID | Expected Keywords in Response |
|----------|------------------------------|
| 4624 | "logon", "successful", "login" |
| 4625 | "failed", "logon", "incorrect password" |
| 4648 | "explicit credentials", "alternate" |
| 7045 | "service", "installed" |
| 4688 | "process", "created", "started" |
| 4672 | "special privileges", "admin" |

### Validation Steps

- [ ] Ask "What is event 4624?"
- [ ] Verify response contains logon-related keywords
- [ ] Verify same question always gives consistent answer
- [ ] Ask "Explain event 4625" - verify different from 4624
- [ ] Verify sources are shown (event KB reference)

---

## 5. Offline-Only Compliance

### Validation Steps

- [ ] Disconnect from internet
- [ ] Send "What's my security status?" - should still work
- [ ] Ask "What is event 4624?" - should still work
- [ ] Ask "How do I use Sentinel?" - should still work
- [ ] Verify no network errors in console

### Network Monitoring

- [ ] Run with network monitor (e.g., Wireshark)
- [ ] Verify zero outbound connections from assistant features
- [ ] All responses come from local sources only

---

## 6. Response Structure Validation

### Required Fields in Structured Response

| Field | Required | Description |
|-------|----------|-------------|
| `answer` | Yes | Main answer text |
| `context` | No | What it means / simple explanation |
| `actions` | No | List of recommended actions |
| `sources` | No | List of source references |
| `confidence` | Yes | HIGH / MEDIUM / LOW |
| `technical_details` | No | Optional technical info |

### Validation Steps

- [ ] Check response structure in browser console (F12)
- [ ] Verify confidence badge shows correctly
- [ ] Verify "Show details" toggle works
- [ ] Verify sources list appears when available

---

## 7. Performance Benchmarks

### Target Metrics

| Operation | Target Time |
|-----------|-------------|
| Intent classification | < 50ms |
| Memory context retrieval | < 10ms |
| Local retrieval (TF-IDF) | < 100ms |
| PowerShell query (Defender) | < 1000ms |
| PowerShell query (Firewall) | < 500ms |
| Full response generation | < 2000ms |

### Validation Steps

- [ ] Enable performance profiling (check console output)
- [ ] Send 10 queries of different types
- [ ] Record timing for each
- [ ] Verify all within target times

---

## 8. Cache Behavior

### Test Cases

| Scenario | Expected Behavior |
|----------|------------------|
| Same query twice | Second response is cached (faster) |
| Query after state change | Cache miss, fresh response |
| Query after 5+ minutes | Cache expired, fresh response |

### Validation Steps

- [ ] Ask "What is event 4624?" - note response time
- [ ] Ask same question again - should be faster
- [ ] Clear chat and ask again - should still be cached (conversation cleared, not cache)
- [ ] Check console for cache hit/miss logs

---

## 9. Error Handling

### Test Cases

| Scenario | Expected Behavior |
|----------|------------------|
| Invalid PowerShell output | Graceful fallback to generic response |
| Missing docs folder | App still works, just fewer sources |
| Unknown intent | Falls back to general security QA |

### Validation Steps

- [ ] Ask something completely random - verify no crash
- [ ] Verify error messages are user-friendly
- [ ] Verify app remains stable after errors

---

## 10. Quick Suggestions

### Test Cases

| Suggestion | Expected Result |
|-----------|-----------------|
| "What's my security status?" | Full security overview |
| "Explain recent events" | Summary of recent Windows events |
| "Is my firewall enabled?" | Firewall status check |
| "Any security concerns?" | Security assessment |

### Validation Steps

- [ ] Click each quick suggestion button
- [ ] Verify appropriate response is generated
- [ ] Verify suggestion buttons remain functional after use

---

## Sign-off

| Validation Area | Pass/Fail | Tester | Date |
|-----------------|-----------|--------|------|
| Conversation Memory | | | |
| Intent Classification | | | |
| UI Responsiveness | | | |
| Event Explanations | | | |
| Offline Compliance | | | |
| Response Structure | | | |
| Performance | | | |
| Cache Behavior | | | |
| Error Handling | | | |
| Quick Suggestions | | | |

---

## Notes

- All tests should be run with `SENTINEL_ENABLE_LLM=0` (default) to verify rule-based system works
- For LLM-enhanced testing, set `SENTINEL_ENABLE_LLM=1` and ensure CUDA GPU is available
- Log files can be found in app logs for debugging
