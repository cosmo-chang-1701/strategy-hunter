# --- 應用程式狀態管理 ---
# 使用一個類別來管理應用程式的狀態，使其更具結構性


class AppState:
    """一個簡單的類別來管理應用程式的共享狀態。"""

    def __init__(self):
        self._state = {}

    def __getitem__(self, key):
        """允許使用字典風格的語法獲取狀態值 (e.g., app_state['my_key'])"""
        return self._state.get(key)

    def __setitem__(self, key, value):
        """允許使用字典風格的語法設定狀態值 (e.g., app_state['my_key'] = my_value)"""
        self._state[key] = value

    def get(self, key, default=None):
        """提供一個安全的 get 方法，類似於字典的 get。"""
        return self._state.get(key, default)

    def clear(self):
        """清除所有儲存的狀態。"""
        self._state.clear()
        print("INFO:     Application state cleared.")


# 建立 AppState 的單一實例，在整個應用程式中共享
app_state = AppState()
