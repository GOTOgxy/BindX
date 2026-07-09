# Mouse Remapper Logic

这是 BindX 内联的鼠标/按键映射业务模块，负责底层 hook、触发匹配和输出模拟。

当前目录不再单独提供 GUI、启动脚本或独立配置文件；运行与配置统一由 BindX 主程序负责。

## 安装

```bash
pip install -r requirements.txt
```

## 使用

双击 `mouse_remapper.bat` 或运行：

```bash
python app.py
```

### 功能

- 键盘快捷键重映射（如 Ctrl+P → Ctrl+Alt+W）
- 鼠标按键重映射（如侧键X1 → Ctrl+W）
- 每个映射可单独启用/禁用
- 可视化添加/编辑/删除映射
- 支持录制按键组合
- 系统托盘图标，最小化到托盘

## 项目结构

```
app.py               # 入口
engine.py            # 核心引擎
gui.py               # 图形界面
config.json          # 配置文件
mouse_remapper.bat   # 启动脚本
```

## 配置文件

`config.json` 示例：

```json
{
  "mappings": [
    {
      "trigger": ["ctrl", "p"],
      "output": ["ctrl", "alt", "w"],
      "description": "Ctrl+P -> Ctrl+Alt+W",
      "enabled": true
    }
  ],
  "mouse_mappings": [
    {
      "button": "x1",
      "output": ["ctrl", "w"],
      "description": "鼠标侧键X1 -> Ctrl+W",
      "enabled": true
    }
  ]
}
```

## 支持的按键

**修饰键：** `ctrl`, `shift`, `alt`, `cmd`

**字母/数字：** `a-z`, `0-9`

**特殊键：** `space`, `tab`, `enter`, `esc`, `backspace`, `delete`, `up`, `down`, `left`, `right`, `home`, `end`, `page_up`, `page_down`, `f1-f12`

**鼠标按键：** `left`, `right`, `middle`, `x1`, `x2`
