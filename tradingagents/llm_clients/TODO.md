# LLM 客户端 - 一致性改进

## 待修复问题

### 1. `validate_model()` 从未被调用
- 在 `get_llm()` 中添加验证调用，对未知模型发出警告（不是错误）

### 2. 参数处理不一致
| 客户端 | API 密钥参数 | 特殊参数 |
|--------|---------------|----------------|
| OpenAI | `api_key` | `reasoning_effort` |
| Anthropic | `api_key` | `thinking_config` → `thinking` |
| Google | `google_api_key` | `thinking_budget` |

**修复：** 使用统一的 `api_key` 标准化，映射到提供商特定的密钥

### 3. `base_url` 被接受但被忽略
- `AnthropicClient`：接受 `base_url` 但从未使用
- `GoogleClient`：接受 `base_url` 但从未使用（正确 - Google 不支持）

**修复：** 从不支持它的客户端中删除未使用的 `base_url`

### 4. 使用 CLI 模型更新 validators.py
- 在功能 2 完成后，将 `VALID_MODELS` 字典与 CLI 模型选项同步
