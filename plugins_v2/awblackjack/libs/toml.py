import os
import tomllib


def read(file_path) -> dict:
    """读取 toml 文件"""
    if not os.path.exists(file_path):
        return {}
    with open(file_path, "rb") as f:
        return tomllib.load(f)


class Config:
    def __init__(self, path, default_path):
        self.config = read(path)
        self.config_default = read(default_path)

    def get(self, key: str, default=None):
        """获取配置值，支持任意层级的点分路径，不区分大小写"""
        if not key:
            raise KeyError("Empty key provided")

        try:
            if self.config:
                return self._lookup_key(self.config, key)
        except KeyError:
            pass

        return self._get_from_default(key, default)

    def _get_from_default(self, key: str, default=None):
        """从默认配置中获取值，如果没有则抛出 KeyError"""
        if not self.config_default:
            raise KeyError(f"Key '{key}' not found in config or default config")
        return self._lookup_key(self.config_default, key, default)

    def _lookup_key(self, config_dict: dict, key: str, default=None):
        """内部查找key的公共方法"""
        keys = key.lower().split(".")
        current = config_dict

        for k in keys:
            if not isinstance(current, dict):
                if default:
                    return default
                raise KeyError(f"Key '{key}' not found")

            # 在当前层级查找不区分大小写的匹配
            matched = None
            for actual_key in current.keys():
                if actual_key.lower() == k:
                    matched = actual_key
                    break

            if matched is None:
                if default:
                    return default
                raise KeyError(f"Key '{key}' not found")

            current = current[matched]

        return current


config = Config("config/config_new.toml", "config/config_example.toml")
if __name__ == "__main__":
    try:
        print(config.get("GAME.AFK.bonus"))
    except KeyError as e:
        print(f"Error: {e}")
