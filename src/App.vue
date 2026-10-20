<template>
  <div class="app-container" :data-theme="config.app?.theme || 'light'">
    <!-- Top Titlebar / Header (Borderless Unified) -->
    <header 
      class="app-header" 
      data-tauri-drag-region 
      @mousedown="onHeaderMouseDown" 
      @dblclick="onHeaderDblClick"
    >
      <div class="brand" data-tauri-drag-region>
        <div class="logo-box" data-tauri-drag-region>
          <img :src="appIcon" class="brand-icon" alt="BindX Icon" />
        </div>
        <div class="brand-text" data-tauri-drag-region>
          <span class="title" data-tauri-drag-region>BindX</span>
          <span class="version-tag" data-tauri-drag-region>v2.0.2</span>
        </div>
      </div>

      <!-- Drag spacer between brand and status -->
      <div class="header-drag-spacer" data-tauri-drag-region></div>

      <div class="header-status" data-tauri-drag-region>
        <!-- Hotkey Engine Pill -->
        <div class="status-pill" :class="{ active: config.app.hotkey_running }">
          <span class="dot"></span>
          <span>快捷键: {{ config.app.hotkey_running ? '运行中' : '已停止' }}</span>
          <label class="toggle-switch mini">
            <input type="checkbox" v-model="config.app.hotkey_running" @change="onToggleHotkeyEngine" />
            <span class="slider"></span>
          </label>
        </div>

        <!-- Mouse Remap Pill -->
        <div class="status-pill" :class="{ active: config.app.mouse_running }">
          <span class="dot"></span>
          <span>侧键映射: {{ config.app.mouse_running ? '运行中' : '已停止' }}</span>
          <label class="toggle-switch mini">
            <input type="checkbox" v-model="config.app.mouse_running" @change="onToggleMouseEngine" />
            <span class="slider"></span>
          </label>
        </div>

        <!-- Autostart Badge -->
        <div class="badge-pill" :class="{ enabled: config.app.autostart_enabled }">
          自启: {{ config.app.autostart_enabled ? '开' : '关' }}
        </div>
      </div>

      <!-- Drag spacer between status and window controls -->
      <div class="header-drag-spacer" data-tauri-drag-region></div>

      <!-- Theme Switcher & Window Control Buttons -->
      <div class="header-actions">
        <button 
          class="theme-toggle-btn" 
          title="切换外观主题"
          @click="toggleTheme"
        >
          <Sun v-if="(config.app?.theme || 'light') === 'light'" class="w-3.5 h-3.5 text-amber-500" />
          <Moon v-else class="w-3.5 h-3.5 text-indigo-400" />
          <span class="theme-label">{{ (config.app?.theme || 'light') === 'slate' ? '灰蓝' : '浅色' }}</span>
        </button>

        <div class="window-controls">
          <button class="win-btn" title="最小化" @click="minimizeWindow">
            <Minus class="w-3.5 h-3.5" />
          </button>
          <button class="win-btn" title="最大化/还原" @click="toggleMaximize">
            <Square class="w-3 h-3" />
          </button>
          <button class="win-btn win-close" title="收起至托盘" @click="hideWindow">
            <X class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </header>

    <!-- Main Workspace Layout -->
    <div class="app-body">
      <!-- Sidebar Navigation -->
      <nav class="sidebar" :style="{ width: `${sidebarWidth}px` }">
        <button 
          v-for="item in navItems" 
          :key="item.id"
          class="nav-tab" 
          :class="{ active: currentTab === item.id }"
          @click="currentTab = item.id"
        >
          <component :is="item.icon" class="tab-icon" />
          <span class="tab-label">{{ item.label }}</span>
          <span v-if="item.badge" class="nav-badge">{{ item.badge }}</span>
        </button>

        <div class="sidebar-footer">
          <div class="cloud-indicator" @click="currentTab = 'webdav'">
            <div class="indicator-icon-wrap">
              <Cloud class="w-4 h-4 indicator-icon" />
            </div>
            <div class="indicator-info">
              <span class="label">云同步</span>
              <div class="val-row">
                <span class="indicator-dot" :class="config.webdav.server_url ? 'online' : 'offline'"></span>
                <span class="val">{{ config.webdav.server_url ? '已连接' : '未配置' }}</span>
              </div>
            </div>
          </div>
        </div>
      </nav>

      <!-- Sidebar Resizer Splitter -->
      <div 
        class="sidebar-resizer" 
        :class="{ resizing: isResizingSidebar }"
        @mousedown="startSidebarResize"
        @dblclick="resetSidebarWidth"
        title="按住左右拖动调节侧边栏宽度，双击恢复默认"
      >
        <div class="resizer-line"></div>
      </div>

      <!-- Content Area -->
      <main class="content-panel">
        <!-- Alert Toast -->
        <transition name="fade">
          <div v-if="toast.show" class="toast-banner" :class="toast.type">
            <div class="toast-content">
              <span>{{ toast.message }}</span>
            </div>
            <button class="toast-close" @click="toast.show = false">×</button>
          </div>
        </transition>

        <!-- 1. 概览 (Overview) -->
        <div v-if="currentTab === 'overview'" class="tab-pane">
          <div class="pane-header">
            <div>
              <h2>概览</h2>
              <p class="subtitle">监视快捷键与输入映射的运行状态</p>
            </div>
            <div class="actions">
              <button class="btn btn-secondary" @click="fetchConfig">刷新</button>
              <button class="btn btn-primary" @click="saveAll">保存设置</button>
            </div>
          </div>

          <!-- KPI Metrics Row -->
          <div class="kpi-row">
            <div class="glass-panel kpi-card">
              <div class="kpi-icon-wrap hotkey-accent">
                <Keyboard class="w-5 h-5 text-indigo-500" />
              </div>
              <div class="kpi-info">
                <span class="kpi-label">全局快捷键</span>
                <div class="kpi-value-row">
                  <span class="kpi-value">{{ config.hotkeys.entries.length }}</span>
                  <span class="kpi-unit">项 (已启用 {{ activeHotkeysCount }})</span>
                </div>
              </div>
            </div>

            <div class="glass-panel kpi-card">
              <div class="kpi-icon-wrap remap-accent">
                <MousePointer class="w-5 h-5 text-pink-500" />
              </div>
              <div class="kpi-info">
                <span class="kpi-label">按键映射</span>
                <div class="kpi-value-row">
                  <span class="kpi-value">{{ config.mouse.mappings.length }}</span>
                  <span class="kpi-unit">条规则</span>
                </div>
              </div>
            </div>

            <div class="glass-panel kpi-card">
              <div class="kpi-icon-wrap cloud-accent">
                <Cloud class="w-5 h-5 text-cyan-500" />
              </div>
              <div class="kpi-info">
                <span class="kpi-label">云端同步</span>
                <div class="kpi-value-row">
                  <span class="kpi-status-dot" :class="config.webdav.server_url ? 'online' : 'offline'"></span>
                  <span class="kpi-text-val">{{ config.webdav.server_url ? '已连接' : '未配置' }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Hero Engine Cards -->
          <div class="grid-cards mt-5">
            <!-- Hotkey Engine Card -->
            <div class="glass-panel glass-panel-hover engine-card">
              <div class="card-header">
                <div class="card-icon-title">
                  <div class="engine-avatar hotkey-grad">
                    <Keyboard class="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h3>快捷键服务</h3>
                    <p>全局快捷键监听与窗口激活</p>
                  </div>
                </div>
                <label class="toggle-switch">
                  <input type="checkbox" v-model="config.app.hotkey_running" @change="onToggleHotkeyEngine" />
                  <span class="slider"></span>
                </label>
              </div>

              <div class="card-body">
                <div class="stat-row">
                  <span class="stat-name">已启用</span>
                  <span class="stat-value">{{ activeHotkeysCount }} / {{ config.hotkeys.entries.length }} 项</span>
                </div>
                <div class="stat-row">
                  <span class="stat-name">状态</span>
                  <span class="status-tag" :class="config.app.hotkey_running ? 'online' : 'offline'">
                    {{ config.app.hotkey_running ? '运行中' : '已暂停' }}
                  </span>
                </div>
              </div>

              <div class="card-footer">
                <button class="btn btn-secondary w-full" @click="currentTab = 'hotkeys'">
                  <span>管理快捷键</span>
                  <ArrowRight class="w-4 h-4 ml-1" />
                </button>
              </div>
            </div>

            <!-- Mouse Remap Engine Card -->
            <div class="glass-panel glass-panel-hover engine-card">
              <div class="card-header">
                <div class="card-icon-title">
                  <div class="engine-avatar mouse-grad">
                    <MousePointer class="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h3>按键映射服务</h3>
                    <p>鼠标侧键与键盘组合键统一分派</p>
                  </div>
                </div>
                <label class="toggle-switch">
                  <input type="checkbox" v-model="config.app.mouse_running" @change="onToggleMouseEngine" />
                  <span class="slider"></span>
                </label>
              </div>

              <div class="card-body">
                <div class="stat-row">
                  <span class="stat-name">已配置规则</span>
                  <span class="stat-value">{{ config.mouse.mappings.length }} 项</span>
                </div>
                <div class="stat-row">
                  <span class="stat-name">状态</span>
                  <span class="status-tag" :class="config.app.mouse_running ? 'online' : 'offline'">
                    {{ config.app.mouse_running ? '运行中' : '已暂停' }}
                  </span>
                </div>
              </div>

              <div class="card-footer">
                <button class="btn btn-secondary w-full" @click="currentTab = 'remap'">
                  <span>管理映射</span>
                  <ArrowRight class="w-4 h-4 ml-1" />
                </button>
              </div>
            </div>
          </div>

          <!-- Bottom Integrations Section -->
          <div class="grid-cards mt-5">
            <!-- WebDAV Quick Card -->
            <div class="glass-panel integration-card">
              <div class="integration-header">
                <div class="integration-icon-wrap cloud-wrap">
                  <Cloud class="w-5 h-5 text-cyan-500" />
                </div>
                <div>
                  <h4 class="integration-title">云端配置同步</h4>
                  <p class="integration-desc">多设备共享快捷键配置</p>
                </div>
              </div>
              <div class="integration-meta">
                <div class="meta-item">
                  <span class="meta-label">服务器</span>
                  <span class="meta-val font-mono">{{ config.webdav.server_url || '未配置' }}</span>
                </div>
                <div class="meta-item">
                  <span class="meta-label">远程路径</span>
                  <span class="meta-val font-mono">{{ config.webdav.remote_filename || '未设置' }}</span>
                </div>
              </div>
              <div class="integration-actions">
                <button class="btn btn-primary" :disabled="downloadingWebDav" @click="onDownloadWebDav">
                  <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': downloadingWebDav }" />
                  <span>立即同步</span>
                </button>
                <button class="btn btn-secondary" @click="currentTab = 'webdav'">同步设置</button>
              </div>
            </div>

            <!-- Client Environment Card -->
            <div class="glass-panel integration-card">
              <div class="integration-header">
                <div class="integration-icon-wrap update-wrap">
                  <ShieldCheck class="w-5 h-5 text-indigo-500" />
                </div>
                <div>
                  <h4 class="integration-title">运行环境</h4>
                  <p class="integration-desc">绿色单文件免安装架构</p>
                </div>
              </div>
              <div class="integration-meta">
                <div class="meta-item">
                  <span class="meta-label">当前版本</span>
                  <span class="meta-val font-mono text-indigo-600 font-semibold">v2.0.2</span>
                </div>
                <div class="meta-item">
                  <span class="meta-label">开机自启</span>
                  <span class="meta-val">{{ config.app.autostart_enabled ? '已开启' : '未开启' }}</span>
                </div>
              </div>
              <div class="integration-actions">
                <button class="btn btn-secondary" @click="onCheckUpdate">检查更新</button>
                <button class="btn btn-secondary" @click="currentTab = 'settings'">设置</button>
              </div>
            </div>
          </div>
        </div>

        <!-- 2. 快捷键 (Hotkeys) -->
        <div v-if="currentTab === 'hotkeys'" class="tab-pane">
          <div class="pane-header">
            <div>
              <h2>快捷键</h2>
              <p class="subtitle">绑定全局快捷键以呼出或切换指定应用与网页</p>
            </div>
            <div class="actions">
              <button class="btn btn-primary" @click="openAddHotkeyModal">+ 添加快捷键</button>
            </div>
          </div>

          <div class="glass-panel overflow-hidden">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 70px;">状态</th>
                  <th>快捷键</th>
                  <th>目标应用</th>
                  <th>类型</th>
                  <th>行为</th>
                  <th style="width: 110px;">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(entry, index) in config.hotkeys.entries" :key="index">
                  <td>
                    <label class="toggle-switch mini">
                      <input type="checkbox" v-model="entry.enabled" @change="saveAll" />
                      <span class="slider"></span>
                    </label>
                  </td>
                  <td>
                    <span class="keycap">{{ entry.hotkey }}</span>
                  </td>
                  <td>
                    <div class="flex items-center gap-2">
                      <span class="font-medium text-slate-200">{{ entry.name || entry.app }}</span>
                      <span v-if="entry.title_keyword" class="text-xs text-slate-400">
                        ({{ entry.title_keyword }})
                      </span>
                    </div>
                  </td>
                  <td>
                    <span class="type-pill" :class="entry.target_type || 'win32'">
                      {{ formatTargetType(entry.target_type) }}
                    </span>
                  </td>
                  <td>
                    <span class="text-xs text-slate-400">
                      {{ formatBehavior(entry._runtime_profile) }}
                    </span>
                  </td>
                  <td>
                    <div class="table-actions">
                      <button class="btn-icon" title="编辑" @click="editHotkey(entry, index)">
                        <Edit class="w-3.5 h-3.5" />
                      </button>
                      <button class="btn-icon danger" title="删除" @click="deleteHotkey(index)">
                        <Trash2 class="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 3. 按键映射 (Remap) -->
        <div v-if="currentTab === 'remap'" class="tab-pane">
          <div class="pane-header">
            <div>
              <h2>按键映射</h2>
              <p class="subtitle">配置鼠标侧键与键盘组合键的操作映射</p>
            </div>
            <div class="actions">
              <button class="btn btn-primary" @click="saveAll">保存设置</button>
            </div>
          </div>

          <!-- Key Detector & Tester Card -->
          <div class="glass-panel detector-card">
            <div class="detector-header">
              <div class="card-icon-title">
                <div class="section-icon-wrap detector-wrap">
                  <Radio class="w-5 h-5 text-indigo-500" />
                </div>
                <div>
                  <h3 class="section-title">按键检测</h3>
                  <p class="section-desc">点击下方测试框并按下键盘或鼠标侧键，实时识别按键输入</p>
                </div>
              </div>
              <div class="detector-actions">
                <button v-if="detectedKeys.length > 0" class="btn btn-secondary text-xs" @click="clearDetectedKeys">
                  清空
                </button>
                <button 
                  v-if="detectedKeys.length > 0" 
                  class="btn btn-primary text-xs" 
                  @click="createMappingFromDetected"
                >
                  + 以此按键创建映射
                </button>
              </div>
            </div>

            <div 
              class="detector-pad" 
              :class="{ active: isDetectingPadFocused }"
              tabindex="0"
              @focus="onDetectorFocus"
              @blur="onDetectorBlur"
              @keydown="onDetectorKeyDown"
              @pointerdown="onDetectorPointerDown"
              @contextmenu.prevent
            >
              <div v-if="detectedKeys.length > 0" class="detected-keys-display">
                <div class="flex gap-2 items-center flex-wrap justify-center">
                  <template v-for="(k, idx) in detectedKeys" :key="idx">
                    <span v-if="idx > 0" class="detector-plus">+</span>
                    <span 
                      class="keycap detector-keycap"
                      :class="{ mouse: isMouseKey(k) }"
                    >
                      {{ formatKeyLabel(k) }}
                    </span>
                  </template>
                </div>
                <div class="detected-sub-info">
                  <span class="detector-tag">{{ getDetectedKeyDescription(detectedKeys) }}</span>
                  <span class="font-mono text-xs text-muted">标准代码: {{ detectedKeys.join(' ') }}</span>
                </div>
              </div>
              <div v-else class="detector-idle">
                <MousePointer class="w-6 h-6 text-indigo-400 opacity-60 mb-1" />
                <span class="detector-hint-title">点击此处激活按键捕获</span>
                <span class="detector-hint-sub">支持键盘常规按键、修饰键以及鼠标侧键（后退 X1 / 前进 X2 / 滚轮中键）</span>
              </div>
            </div>

            <!-- Presets row -->
            <div class="detector-presets">
              <span class="preset-label">常用快捷预设：</span>
              <div class="preset-chips">
                <button type="button" class="preset-chip" @click="addQuickPreset(['x1'], ['ctrl', 'w'], '鼠标后退键关闭标签')">
                  + 鼠标后退 (X1) → 关闭标签 (Ctrl+W)
                </button>
                <button type="button" class="preset-chip" @click="addQuickPreset(['x2'], ['ctrl', 't'], '鼠标前进键新建标签')">
                  + 鼠标前进 (X2) → 新建标签 (Ctrl+T)
                </button>
                <button type="button" class="preset-chip" @click="addQuickPreset(['x1'], ['alt', 'left'], '鼠标后退键网页后退')">
                  + 鼠标后退 (X1) → 网页后退 (Alt+Left)
                </button>
                <button type="button" class="preset-chip" @click="addQuickPreset(['mbutton'], ['win', 'd'], '滚轮中键显示桌面')">
                  + 滚轮中键 → 显示桌面 (Win+D)
                </button>
              </div>
            </div>
          </div>

          <!-- Unified Key Mapping Table Card -->
          <div class="glass-panel remap-section-card mt-5">
            <div class="section-card-header">
              <div class="card-icon-title">
                <div class="section-icon-wrap key-wrap">
                  <Layers class="w-5 h-5 text-indigo-500" />
                </div>
                <div>
                  <h3 class="section-title">映射规则列表</h3>
                  <p class="section-desc">已生效的鼠标侧键与键盘组合键映射</p>
                </div>
              </div>
              <div class="flex items-center gap-3">
                <div class="engine-badge-pill" :class="{ active: config.app?.mouse_running }">
                  <span class="dot"></span>
                  <span>映射监听: {{ config.app?.mouse_running ? '运行中' : '已暂停' }}</span>
                </div>
                <button class="btn btn-primary text-xs" @click="openAddRemapModal()">+ 添加映射</button>
              </div>
            </div>

            <div class="overflow-hidden rounded-xl border border-color">
              <table class="data-table">
                <thead>
                  <tr>
                    <th style="width: 70px;">状态</th>
                    <th style="width: 220px;">触发按键</th>
                    <th style="width: 40px; text-align: center;"></th>
                    <th style="width: 220px;">输出按键</th>
                    <th>描述</th>
                    <th style="width: 100px; text-align: center;">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(km, idx) in (config.mouse?.mappings || [])" :key="idx">
                    <td>
                      <label class="toggle-switch mini">
                        <input type="checkbox" v-model="km.enabled" @change="saveAll" />
                        <span class="slider"></span>
                      </label>
                    </td>
                    <td>
                      <div class="flex gap-1.5 items-center flex-wrap">
                        <span 
                          v-for="k in (km.trigger || [])" 
                          :key="k" 
                          class="keycap"
                          :class="{ mouse: isMouseKey(k) }"
                        >
                          {{ formatKeyLabel(k) }}
                        </span>
                      </div>
                    </td>
                    <td style="text-align: center;">
                      <ArrowRight class="w-4 h-4 text-slate-400 inline-block" />
                    </td>
                    <td>
                      <div class="flex gap-1.5 items-center flex-wrap">
                        <span v-for="k in (km.output || [])" :key="k" class="keycap accent">{{ formatKeyLabel(k) }}</span>
                      </div>
                    </td>
                    <td>
                      <span class="text-xs text-secondary font-medium">{{ km.description || '无描述' }}</span>
                    </td>
                    <td style="text-align: center;">
                      <div class="flex items-center justify-center gap-1">
                        <button class="btn-icon" title="编辑映射" @click="openEditRemapModal(km, idx)">
                          <Edit class="w-3.5 h-3.5" />
                        </button>
                        <button class="btn-icon danger" title="删除映射" @click="deleteKeyMapping(idx)">
                          <Trash2 class="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                  <tr v-if="!config.mouse?.mappings || config.mouse.mappings.length === 0">
                    <td colspan="6" class="text-center py-10 text-muted text-xs">
                      暂无映射规则，可使用上方的“按键检测”或“常用预设”快速创建
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- 4. 云同步 (Cloud Sync) -->
        <div v-if="currentTab === 'webdav'" class="tab-pane">
          <div class="pane-header">
            <div>
              <h2>云同步</h2>
              <p class="subtitle">通过 WebDAV 在多台设备间同步配置文件</p>
            </div>
            <div class="actions">
              <button class="btn btn-secondary" :disabled="testingWebDav" @click="onTestWebDav">
                <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': testingWebDav }" />
                <span>{{ testingWebDav ? '测试中...' : '测试连接' }}</span>
              </button>
              <button class="btn btn-primary" :disabled="downloadingWebDav" @click="onDownloadWebDav">
                <DownloadCloud class="w-3.5 h-3.5" :class="{ 'animate-spin': downloadingWebDav }" />
                <span>{{ downloadingWebDav ? '同步中...' : '从云端拉取' }}</span>
              </button>
            </div>
          </div>

          <div class="webdav-dashboard-grid">
            <!-- Left: Server Configuration Card -->
            <div class="glass-panel webdav-card">
              <div class="card-section-header">
                <div class="card-icon-title">
                  <div class="section-icon-wrap webdav-blue">
                    <Server class="w-5 h-5 text-indigo-500" />
                  </div>
                  <div>
                    <h3 class="card-title">服务器设置</h3>
                    <p class="card-subtitle">配置 WebDAV 连接地址与登录凭据</p>
                  </div>
                </div>
              </div>

              <!-- Fast presets chips -->
              <div class="preset-section">
                <span class="preset-label">常见服务预设：</span>
                <div class="preset-chips">
                  <button type="button" class="preset-chip" @click="applyWebDavPreset('jianguoyun')">坚果云</button>
                  <button type="button" class="preset-chip" @click="applyWebDavPreset('alist')">Alist 本地/局域网</button>
                  <button type="button" class="preset-chip" @click="applyWebDavPreset('nextcloud')">Nextcloud</button>
                  <button type="button" class="preset-chip" @click="applyWebDavPreset('custom')">自定义服务</button>
                </div>
              </div>

              <div class="form-grid">
                <div class="form-item col-span-2">
                  <label class="form-label">服务器地址</label>
                  <input 
                    type="text" 
                    class="input-field" 
                    placeholder="例如: https://dav.example.com/"
                    v-model="config.webdav.server_url" 
                  />
                  <span class="field-hint">支持 http / https 协议</span>
                </div>

                <div class="form-item">
                  <label class="form-label">用户名</label>
                  <input 
                    type="text" 
                    class="input-field" 
                    placeholder="例如: username"
                    v-model="config.webdav.username" 
                  />
                </div>

                <div class="form-item">
                  <label class="form-label">密码</label>
                  <div class="password-input-wrapper">
                    <input 
                      :type="showPassword ? 'text' : 'password'" 
                      class="input-field password-input" 
                      placeholder="••••••••••••"
                      v-model="config.webdav.password" 
                    />
                    <button 
                      type="button" 
                      class="eye-btn"
                      title="切换显示/隐藏密码"
                      @click="showPassword = !showPassword"
                    >
                      <Eye v-if="!showPassword" class="w-4 h-4" />
                      <EyeOff v-else class="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div class="form-item col-span-2">
                  <label class="form-label">同步目录</label>
                  <input 
                    type="text" 
                    class="input-field font-mono" 
                    placeholder="默认: bindx (留空自动使用默认目录)"
                    v-model="config.webdav.remote_filename" 
                  />
                  <span class="field-hint">仅需指定云端子目录，配置文件由软件内部自动托管</span>
                </div>

                <div class="form-item col-span-2 flex items-center justify-between pt-2">
                  <div>
                    <span class="font-medium text-sm text-main">开机时自动同步</span>
                    <p class="text-xs text-muted">启动后自动拉取并应用云端配置</p>
                  </div>
                  <label class="toggle-switch">
                    <input type="checkbox" v-model="config.webdav.auto_sync_on_startup" />
                    <span class="slider"></span>
                  </label>
                </div>
              </div>

              <div class="card-footer-actions">
                <button class="btn btn-primary" @click="saveAll">保存设置</button>
              </div>
            </div>

            <!-- Right: Operations & Status Card -->
            <div class="glass-panel webdav-card webdav-ops-card">
              <div class="card-section-header">
                <div class="card-icon-title">
                  <div class="section-icon-wrap cloud-blue">
                    <Cloud class="w-5 h-5 text-cyan-500" />
                  </div>
                  <div>
                    <h3 class="card-title">同步操作</h3>
                    <p class="card-subtitle">手动上传或从云端拉取配置</p>
                  </div>
                </div>
              </div>

              <!-- Live Sync Status Banner -->
              <div class="sync-status-box">
                <div class="sync-status-row">
                  <span class="sync-label">连接状态:</span>
                  <span class="status-tag" :class="config.webdav.server_url ? 'online' : 'offline'">
                    {{ config.webdav.server_url ? '已连接' : '未配置' }}
                  </span>
                </div>
                <div class="sync-status-row">
                  <span class="sync-label">同步目录:</span>
                  <span class="font-mono text-xs text-main">{{ remoteDirectory }}</span>
                </div>
                <div class="sync-status-row">
                  <span class="sync-label">托管配置:</span>
                  <span class="text-xs text-muted">软件内部自动托管</span>
                </div>
              </div>

              <!-- Action Buttons with clear descriptions -->
              <div class="sync-actions-list">
                <div class="sync-action-item">
                  <div class="sync-action-desc">
                    <span class="sync-action-title">测试连接</span>
                    <span class="sync-action-sub">检测服务器与凭据有效性</span>
                  </div>
                  <button class="btn btn-secondary" :disabled="testingWebDav" @click="onTestWebDav">
                    <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': testingWebDav }" />
                    <span>{{ testingWebDav ? '测试中...' : '测试连接' }}</span>
                  </button>
                </div>

                <div class="sync-action-item">
                  <div class="sync-action-desc">
                    <span class="sync-action-title">上传配置</span>
                    <span class="sync-action-sub">将当前本地配置推送到云端</span>
                  </div>
                  <button class="btn btn-secondary" :disabled="uploadingWebDav" @click="onUploadWebDav">
                    <Upload class="w-3.5 h-3.5" :class="{ 'animate-spin': uploadingWebDav }" />
                    <span>{{ uploadingWebDav ? '上传中...' : '立即上传' }}</span>
                  </button>
                </div>

                <div class="sync-action-item highlight">
                  <div class="sync-action-desc">
                    <span class="sync-action-title">下载配置</span>
                    <span class="sync-action-sub">拉取云端配置并立即生效</span>
                  </div>
                  <button class="btn btn-primary" :disabled="downloadingWebDav" @click="onDownloadWebDav">
                    <DownloadCloud class="w-3.5 h-3.5" :class="{ 'animate-spin': downloadingWebDav }" />
                    <span>{{ downloadingWebDav ? '同步中...' : '立即下载' }}</span>
                  </button>
                </div>
              </div>

              <!-- Informative hint box -->
              <div class="distribution-tip mt-auto">
                <div class="font-medium text-main text-xs mb-1">说明：</div>
                <p class="text-xs text-muted leading-relaxed">
                  配置保存在 WebDAV 服务器中，实现多设备配置无缝共享。
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- 5. 版本更新 (Updates) -->
        <div v-if="currentTab === 'update'" class="tab-pane">
          <div class="pane-header">
            <div>
              <h2>版本更新</h2>
              <p class="subtitle">检查与下载最新版本</p>
            </div>
            <div class="actions">
              <button class="btn btn-primary" :disabled="checkingUpdate" @click="onCheckUpdate">
                <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': checkingUpdate }" />
                <span>{{ checkingUpdate ? '检查中...' : '检查更新' }}</span>
              </button>
            </div>
          </div>

          <div class="update-dashboard-grid">
            <!-- Left: Version Checker Hero Card -->
            <div class="glass-panel version-hero-card">
              <div class="hero-header-box">
                <div class="flex items-center gap-3.5">
                  <div class="hero-icon-box">
                    <Sparkles class="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h3 class="hero-title">BindX</h3>
                    <p class="hero-ver">当前版本: <span class="font-mono font-semibold text-indigo-600">v2.0.2</span></p>
                  </div>
                </div>
                <div>
                  <span v-if="updateInfo && updateInfo.has_update" class="update-badge has-update">发现新版本</span>
                  <span v-else class="update-badge latest">最新版本</span>
                </div>
              </div>

              <!-- Architecture Specs List -->
              <div class="hero-specs-list">
                <div class="spec-row">
                  <span class="spec-name">运行架构</span>
                  <span class="spec-val">Windows x64</span>
                </div>
                <div class="spec-row">
                  <span class="spec-name">运行规格</span>
                  <span class="spec-val">独立绿色单文件</span>
                </div>
                <div class="spec-row">
                  <span class="spec-name">内存占用</span>
                  <span class="spec-val">约 15 MB</span>
                </div>
                <div class="spec-row">
                  <span class="spec-name">系统调用</span>
                  <span class="spec-val">原生系统钩子</span>
                </div>
              </div>

              <!-- Update Details if available -->
              <div v-if="updateInfo && updateInfo.has_update" class="update-card-content">
                <div class="flex items-baseline justify-between mb-2">
                  <h4 class="text-base font-semibold text-indigo-600">
                    最新版本: {{ updateInfo.latest_version }}
                  </h4>
                  <span class="text-xs text-muted">{{ updateInfo.published_at }}</span>
                </div>

                <div class="changelog-box">
                  <div class="text-xs font-semibold text-secondary uppercase tracking-wider mb-1">更新日志：</div>
                  <pre class="changelog-text">{{ updateInfo.release_notes || '无更新说明' }}</pre>
                </div>

                <div class="flex gap-3 mt-4">
                  <button class="btn btn-success" @click="openUrl(updateInfo.download_url)">
                    <DownloadCloud class="w-4 h-4" />
                    立即下载
                  </button>
                  <button class="btn btn-secondary" @click="openUrl(updateInfo.release_page_url)">
                    发布页面
                  </button>
                </div>
              </div>

              <!-- If already latest or not checked -->
              <div v-else class="py-4 text-center text-muted text-sm flex flex-col items-center gap-2">
                <div class="flex items-center gap-2 text-emerald-600 font-medium">
                  <CheckCircle2 class="w-4 h-4" />
                  <span>当前已是最新版本</span>
                </div>
                <p class="text-xs text-dim">点击下方按钮可重新查询云端发布。</p>
              </div>

              <!-- Direct Check Button -->
              <div class="pt-2">
                <button class="btn btn-secondary w-full" :disabled="checkingUpdate" @click="onCheckUpdate">
                  <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': checkingUpdate }" />
                  <span>{{ checkingUpdate ? '正在检查...' : '重新检查' }}</span>
                </button>
              </div>
            </div>

            <!-- Right: Distribution Architecture Explanations -->
            <div class="glass-panel arch-cards-panel">
              <div class="card-section-header">
                <div class="card-icon-title">
                  <div class="section-icon-wrap system-wrap">
                    <ShieldCheck class="w-5 h-5 text-indigo-500" />
                  </div>
                  <div>
                    <h3 class="card-title">分发架构</h3>
                    <p class="card-subtitle">纯净高效的客户端机制</p>
                  </div>
                </div>
              </div>

              <div class="arch-tiles-list">
                <div class="arch-tile">
                  <div class="arch-icon">🚀</div>
                  <div>
                    <h4 class="arch-title">纯净分发</h4>
                    <p class="arch-desc">无需本地 Git 环境，直接检查并下载可执行文件。</p>
                  </div>
                </div>

                <div class="arch-tile">
                  <div class="arch-icon">☁️</div>
                  <div>
                    <h4 class="arch-title">配置分离</h4>
                    <p class="arch-desc">用户配置由 WebDAV 同步，软件更新不影响已有设置。</p>
                  </div>
                </div>

                <div class="arch-tile">
                  <div class="arch-icon">📦</div>
                  <div>
                    <h4 class="arch-title">绿色便携</h4>
                    <p class="arch-desc">单一可执行文件，开箱即用，无外部依赖。</p>
                  </div>
                </div>

                <div class="arch-tile">
                  <div class="arch-icon">🖥️</div>
                  <div>
                    <h4 class="arch-title">低资源占用</h4>
                    <p class="arch-desc">底层系统原生调用，后台静默运行无额外负担。</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 6. 设置 (Settings) -->
        <div v-if="currentTab === 'settings'" class="tab-pane">
          <div class="pane-header">
            <div>
              <h2>设置</h2>
              <p class="subtitle">外观主题与系统行为偏好</p>
            </div>
            <div class="actions">
              <button class="btn btn-primary" @click="saveAll">保存设置</button>
            </div>
          </div>

          <!-- Section 1: Appearance Themes -->
          <div class="glass-panel settings-section-card">
            <div class="section-card-header">
              <div class="card-icon-title">
                <div class="section-icon-wrap theme-wrap">
                  <Palette class="w-5 h-5 text-indigo-500" />
                </div>
                <div>
                  <h3 class="section-title">外观风格</h3>
                  <p class="section-desc">选择深浅视觉风格</p>
                </div>
              </div>
            </div>

            <div class="theme-options-grid">
              <div 
                class="theme-card-option" 
                :class="{ active: (config.app?.theme || 'light') === 'light' }"
                @click="setTheme('light')"
              >
                <div class="theme-preview light-preview">
                  <Sun class="w-5 h-5 text-amber-500" />
                </div>
                <div class="theme-meta">
                  <span class="name">浅色</span>
                  <span class="desc">默认浅色风格</span>
                </div>
                <div class="theme-check" v-if="(config.app?.theme || 'light') === 'light'">
                  <CheckCircle2 class="w-4 h-4 text-indigo-600" />
                </div>
              </div>

              <div 
                class="theme-card-option" 
                :class="{ active: config.app?.theme === 'slate' }"
                @click="setTheme('slate')"
              >
                <div class="theme-preview slate-preview">
                  <Moon class="w-5 h-5 text-indigo-400" />
                </div>
                <div class="theme-meta">
                  <span class="name">深色</span>
                  <span class="desc">柔和灰蓝风格</span>
                </div>
                <div class="theme-check" v-if="config.app?.theme === 'slate'">
                  <CheckCircle2 class="w-4 h-4 text-cyan-400" />
                </div>
              </div>
            </div>
          </div>

          <!-- Section 2: Windows System Integrations Tiles -->
          <div class="glass-panel settings-section-card mt-6">
            <div class="section-card-header">
              <div class="card-icon-title">
                <div class="section-icon-wrap system-wrap">
                  <Monitor class="w-5 h-5 text-cyan-500" />
                </div>
                <div>
                  <h3 class="section-title">系统选项</h3>
                  <p class="section-desc">开机自启与按键模拟偏好</p>
                </div>
              </div>
            </div>

            <div class="settings-tiles-list">
              <!-- Tile 1: Autostart -->
              <div class="setting-tile">
                <div class="tile-icon-box autostart-box">
                  <Monitor class="w-5 h-5 text-indigo-500" />
                </div>
                <div class="tile-content">
                  <span class="tile-title">开机自动启动</span>
                  <span class="tile-desc">系统登录后自动在托盘后台运行</span>
                </div>
                <div class="tile-action">
                  <label class="toggle-switch">
                    <input type="checkbox" v-model="config.app.autostart_enabled" @change="saveAll" />
                    <span class="slider"></span>
                  </label>
                </div>
              </div>

              <!-- Tile 2: Restore Modifiers -->
              <div class="setting-tile">
                <div class="tile-icon-box keyboard-box">
                  <Keyboard class="w-5 h-5 text-cyan-500" />
                </div>
                <div class="tile-content">
                  <span class="tile-title">自动释放修饰键</span>
                  <span class="tile-desc">模拟按键后自动松开 Ctrl、Alt 等按键，避免粘滞</span>
                </div>
                <div class="tile-action">
                  <label class="toggle-switch">
                    <input type="checkbox" v-model="config.app.restore_held_modifiers" @change="saveAll" />
                    <span class="slider"></span>
                  </label>
                </div>
              </div>

              <!-- Tile 3: Dispatch Delay -->
              <div class="setting-tile">
                <div class="tile-icon-box slider-box">
                  <Sliders class="w-5 h-5 text-purple-500" />
                </div>
                <div class="tile-content">
                  <span class="tile-title">按键模拟延迟</span>
                  <span class="tile-desc">模拟击键间隔时间，推荐 20 ms</span>
                </div>
                <div class="tile-action-slider">
                  <span class="slider-badge">{{ config.app.output_delay_ms }} ms</span>
                  <input 
                    type="range" 
                    min="5" 
                    max="100" 
                    step="5" 
                    v-model.number="config.app.output_delay_ms"
                    class="range-slider"
                    @change="saveAll"
                  />
                </div>
              </div>

              <!-- Tile 4: Config File Path -->
              <div class="setting-tile">
                <div class="tile-icon-box folder-box">
                  <Folder class="w-5 h-5 text-emerald-500" />
                </div>
                <div class="tile-content">
                  <span class="tile-title">配置文件路径</span>
                  <span class="tile-desc">当前生效的本地配置存储位置（{{ configPathInfo.exists ? '文件已生成' : '保存设置后自动生成' }}）</span>
                </div>
                <div class="tile-action-path">
                  <span 
                    class="path-badge" 
                    :title="'点击复制完整路径: ' + (configPathInfo.full_path || '')" 
                    @click="copyConfigPath"
                  >
                    {{ configPathInfo.full_path || '正在读取配置路径...' }}
                  </span>
                  <button class="btn btn-secondary text-xs" title="在资源管理器中高亮定位配置文件" @click="openDataFolder">
                    <FolderOpen class="w-3.5 h-3.5" />
                    <span>打开所在目录</span>
                  </button>
                </div>
              </div>

              <!-- Tile 5: Start Menu & Screen Pinning -->
              <div class="setting-tile">
                <div class="tile-icon-box start-box">
                  <LayoutGrid class="w-5 h-5 text-indigo-500" />
                </div>
                <div class="tile-content">
                  <div class="flex items-center gap-2">
                    <span class="tile-title">固定至「开始」菜单 / 屏幕</span>
                    <span class="status-tag mini" :class="isStartMenuPinned ? 'online' : 'offline'">
                      {{ isStartMenuPinned ? '已加入开始菜单' : '未添加' }}
                    </span>
                  </div>
                  <span class="tile-desc">生成系统应用快捷方式，支持 Win 键搜索瞬间找到 BindX 并一键固定磁贴</span>
                </div>
                <div class="tile-action-buttons">
                  <button 
                    class="btn text-xs" 
                    :class="isStartMenuPinned ? 'btn-secondary' : 'btn-primary'"
                    @click="onToggleStartMenu"
                  >
                    <Pin class="w-3.5 h-3.5 mr-1" />
                    <span>{{ isStartMenuPinned ? '从开始菜单移除' : '添加至开始菜单' }}</span>
                  </button>
                  <button 
                    class="btn btn-secondary text-xs" 
                    title="在开始菜单文件夹中高亮选中 BindX 快捷方式，可右键一键「固定到“开始”屏幕」" 
                    @click="onLocateStartMenu"
                  >
                    <FolderOpen class="w-3.5 h-3.5 mr-1" />
                    <span>在文件夹定位</span>
                  </button>
                </div>
              </div>

              <!-- Tile 6: Desktop Shortcut -->
              <div class="setting-tile">
                <div class="tile-icon-box desktop-box">
                  <ExternalLink class="w-5 h-5 text-cyan-500" />
                </div>
                <div class="tile-content">
                  <span class="tile-title">发送桌面快捷方式</span>
                  <span class="tile-desc">在当前 Windows 桌面上创建快速启动图标</span>
                </div>
                <div class="tile-action">
                  <button class="btn btn-secondary text-xs" @click="onCreateDesktop">
                    <ExternalLink class="w-3.5 h-3.5 mr-1" />
                    <span>创建桌面图标</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>

    <!-- Edit / Add Hotkey Modal -->
    <div v-if="hotkeyModal.show" class="modal-backdrop">
      <div class="modal-dialog glass-panel">
        <div class="modal-header">
          <h3>{{ hotkeyModal.isEdit ? '编辑快捷键' : '添加快捷键' }}</h3>
          <button class="modal-close" @click="closeHotkeyModal">×</button>
        </div>

        <div class="modal-body form-grid">
          <!-- Quick Presets -->
          <div class="form-item col-span-2">
            <label class="form-label">快速应用预设（点击自动填充）</label>
            <div class="preset-chips">
              <button 
                type="button" 
                class="preset-chip preset-chip-primary" 
                @click="applyHotkeyPreset('bindx')"
              >
                ⚡ BindX (本软件主窗口)
              </button>
              <button 
                type="button" 
                class="preset-chip" 
                @click="applyHotkeyPreset('cloudmusic')"
              >
                网易云音乐
              </button>
              <button 
                type="button" 
                class="preset-chip" 
                @click="applyHotkeyPreset('wechat')"
              >
                微信
              </button>
              <button 
                type="button" 
                class="preset-chip" 
                @click="applyHotkeyPreset('termius')"
              >
                Termius
              </button>
              <button 
                type="button" 
                class="preset-chip" 
                @click="applyHotkeyPreset('zotero')"
              >
                Zotero
              </button>
              <button 
                type="button" 
                class="preset-chip" 
                @click="applyHotkeyPreset('vscode')"
              >
                VS Code
              </button>
              <button 
                type="button" 
                class="preset-chip" 
                @click="applyHotkeyPreset('terminal')"
              >
                Windows Terminal
              </button>
              <button 
                type="button" 
                class="preset-chip" 
                @click="applyHotkeyPreset('browser_tab')"
              >
                网页标签页
              </button>
            </div>
          </div>

          <!-- Hotkey Recording & Manual Input Section -->
          <div class="form-item col-span-2">
            <div class="flex items-center justify-between mb-1.5">
              <label class="form-label mb-0">快捷键组合 (支持录制与手动输入)</label>
              <div class="flex items-center gap-2">
                <span v-if="isRecordingHotkey" class="badge-recording">
                  <span class="recording-dot"></span>
                  录制中 (系统热键已隔离)
                </span>
                <button 
                  type="button" 
                  class="btn btn-xs" 
                  :class="isRecordingHotkey ? 'btn-danger' : 'btn-secondary'"
                  @click="toggleHotkeyRecording"
                >
                  {{ isRecordingHotkey ? '⏹ 结束录制' : '⏺ 点击录制按键' }}
                </button>
                <button 
                  v-if="hotkeyModal.data.hotkey" 
                  type="button" 
                  class="btn btn-xs btn-secondary" 
                  @click="hotkeyModal.data.hotkey = ''"
                >
                  清空
                </button>
              </div>
            </div>

            <!-- Manual Editable Input Field -->
            <div class="relative flex items-center mb-2">
              <input 
                type="text" 
                class="input-field font-mono font-medium pr-10" 
                placeholder="请录制按键或直接在此输入（例如: CTRL+ALT+W 或 ALT+SPACE）"
                v-model="hotkeyModal.data.hotkey"
                @focus="onHotkeyInputFocus"
              />
              <button 
                type="button" 
                class="btn-icon absolute right-2 text-indigo-500" 
                :title="isRecordingHotkey ? '点击结束录制' : '点击开始键盘录制'"
                @click="toggleHotkeyRecording"
              >
                <Keyboard class="w-4 h-4" />
              </button>
            </div>

            <!-- Interactive Hotkey Recording Pad -->
            <div 
              class="key-record-box" 
              :class="{ recording: isRecordingHotkey, active: isHotkeyBoxFocused }"
              tabindex="0"
              @focus="onHotkeyBoxFocus"
              @blur="onHotkeyBoxBlur"
              @keydown="onHotkeyRecordKeyDown"
            >
              <div v-if="hotkeyModal.data.hotkey" class="flex items-center gap-1.5 flex-wrap">
                <template v-for="(k, idx) in hotkeyModal.data.hotkey.split('+')" :key="idx">
                  <span v-if="idx > 0" class="text-xs text-muted font-bold">+</span>
                  <span class="keycap">{{ k.trim() }}</span>
                </template>
                <span v-if="isRecordingHotkey" class="text-xs text-indigo-500 font-medium ml-2">
                  (录制中：可随时再次按下以覆盖重录，完成后点击上方“结束录制”)
                </span>
              </div>
              <div v-else-if="isRecordingHotkey" class="text-xs text-indigo-500 font-medium flex items-center gap-2">
                <span class="recording-dot"></span>
                <span>请在键盘上按下目标组合键（支持连续按下多次以覆盖）...</span>
              </div>
              <div v-else class="text-xs text-muted flex items-center gap-2">
                <Radio class="w-3.5 h-3.5 text-indigo-400" />
                <span>点击“点击录制按键”即可直接按下键盘，或在上方输入框直接打字输入</span>
              </div>
            </div>
          </div>

          <div class="form-item">
            <label class="form-label">显示名称</label>
            <input 
              type="text" 
              class="input-field" 
              placeholder="例如: 网易云音乐"
              v-model="hotkeyModal.data.name"
            />
          </div>

          <div class="form-item">
            <label class="form-label">目标类型</label>
            <select 
              class="input-field" 
              :value="hotkeyModal.data.target_type === 'browser_tab' ? 'browser_tab' : 'win32'"
              @change="e => onTargetTypeChange(e.target.value)"
            >
              <option value="win32">桌面客户端 (可执行程序)</option>
              <option value="browser_tab">网页标签页 (按标题匹配)</option>
            </select>
          </div>

          <div v-if="hotkeyModal.data.target_type !== 'browser_tab'" class="form-item">
            <label class="form-label">切换行为</label>
            <select class="input-field" v-model="hotkeyModal.data._runtime_profile.hide_behavior">
              <option value="minimize">最小化切换 (默认，前台再次按下最小化)</option>
              <option value="tray">托盘切换 (适用于网易云音乐、微信等后台软件)</option>
              <option value="hide">窗口隐藏 (SW_HIDE 直接隐藏)</option>
            </select>
          </div>
          <div v-else class="form-item">
            <label class="form-label">切换行为</label>
            <select class="input-field" v-model="hotkeyModal.data._runtime_profile.hide_behavior">
              <option value="minimize">最小化切换 (前台再次按下最小化)</option>
              <option value="hide">窗口隐藏 (SW_HIDE 直接隐藏)</option>
            </select>
          </div>

          <!-- When target_type is browser_tab -->
          <template v-if="hotkeyModal.data.target_type === 'browser_tab'">
            <div class="form-item col-span-2">
              <label class="form-label">标签页标题关键字 (必填)</label>
              <input 
                type="text" 
                class="input-field" 
                placeholder="例如: 千问、Gemini、Bilibili、知乎"
                v-model="hotkeyModal.data.title_keyword"
              />
              <span class="field-hint">
                浏览器会将活动标签页标题显示在窗口上。输入网页标题中的任意关键字，即可瞬间呼出对应窗口。
              </span>
            </div>

            <div class="form-item col-span-2">
              <label class="form-label">所属浏览器进程</label>
              <select class="input-field" v-model="browserPresetSelection" @change="onBrowserPresetChange">
                <option value="auto">自动匹配所有浏览器 (默认推荐，无需关心是 Edge 还是 Chrome)</option>
                <option value="msedge.exe">Microsoft Edge (msedge.exe)</option>
                <option value="chrome.exe">Google Chrome (chrome.exe)</option>
                <option value="custom">其他自定义浏览器进程...</option>
              </select>
            </div>

            <div v-if="browserPresetSelection === 'custom'" class="form-item col-span-2">
              <label class="form-label">自定义浏览器进程文件名</label>
              <input 
                type="text" 
                class="input-field" 
                placeholder="例如: brave.exe、firefox.exe、360chrome.exe"
                v-model="hotkeyModal.data.exe_name"
              />
              <span class="field-hint">限定只在该浏览器进程中查找网页</span>
            </div>
          </template>

          <!-- When target_type is NOT browser_tab -->
          <template v-else>
            <div class="form-item col-span-2">
              <label class="form-label">程序进程文件名</label>
              <input 
                type="text" 
                class="input-field" 
                placeholder="例如: cloudmusic.exe，留空可从路径自动推断"
                v-model="hotkeyModal.data.exe_name"
              />
            </div>

            <div class="form-item col-span-2">
              <label class="form-label">程序路径 (可选)</label>
              <div class="flex gap-2">
                <input 
                  type="text" 
                  class="input-field flex-1" 
                  placeholder="例如: D:\Program Files\App\app.exe (可留空自动识别)"
                  v-model="hotkeyModal.data.install_path"
                />
                <button type="button" class="btn btn-secondary whitespace-nowrap" @click="pickExecutableFile">
                  <FolderOpen class="w-4 h-4 mr-1" />
                  <span>浏览...</span>
                </button>
              </div>
              <span class="field-hint">点击“浏览”可通过 Windows 原生文件窗口选择本地 .exe 文件</span>
            </div>

            <div class="form-item col-span-2 flex items-center justify-between pt-1">
              <div>
                <span class="font-medium text-sm text-main">程序未运行时自动启动</span>
                <p class="text-xs text-muted">按下快捷键时若应用未运行，自动启动程序</p>
              </div>
              <label class="toggle-switch">
                <input type="checkbox" v-model="hotkeyModal.data.launch_if_not_running" />
                <span class="slider"></span>
              </label>
            </div>
          </template>
        </div>

        <div class="modal-footer">
          <button class="btn btn-secondary" @click="closeHotkeyModal">取消</button>
          <button class="btn btn-primary" @click="saveHotkeyModal">保存</button>
        </div>
      </div>
    </div>

    <!-- Edit / Add Remap Modal -->
    <div v-if="remapModal.show" class="modal-backdrop">
      <div class="modal-dialog glass-panel">
        <div class="modal-header">
          <h3>{{ remapModal.isEdit ? '编辑按键映射' : '添加按键映射' }}</h3>
          <button class="modal-close" @click="closeRemapModal">×</button>
        </div>

        <div class="modal-body form-grid">
          <!-- Trigger Section -->
          <div class="form-item col-span-2">
            <div class="flex items-center justify-between mb-1.5">
              <label class="form-label mb-0">触发按键 (Trigger - 支持录制与手动输入)</label>
              <div class="flex items-center gap-2">
                <span v-if="isRecordingTrigger" class="badge-recording">
                  <span class="recording-dot"></span>
                  录制中 (系统热键已隔离)
                </span>
                <button 
                  type="button" 
                  class="btn btn-xs" 
                  :class="isRecordingTrigger ? 'btn-danger' : 'btn-secondary'"
                  @click="toggleTriggerRecording"
                >
                  {{ isRecordingTrigger ? '⏹ 结束录制' : '⏺ 点击录制触发键' }}
                </button>
                <button 
                  v-if="remapModal.data.trigger && remapModal.data.trigger.length > 0" 
                  type="button" 
                  class="btn btn-xs btn-secondary" 
                  @click="remapModal.data.trigger = []"
                >
                  清空
                </button>
              </div>
            </div>

            <!-- Manual Editable Input Field for Trigger -->
            <div class="relative flex items-center mb-2">
              <input 
                type="text" 
                class="input-field font-mono text-sm pr-10" 
                placeholder="例如: x1 或 ctrl+x1 (支持手动输入/修改代码，用 + 分隔)"
                :value="remapModal.data.trigger ? remapModal.data.trigger.join('+') : ''"
                @input="e => onRemapTriggerTextInput(e.target.value)"
              />
              <button 
                type="button" 
                class="btn-icon absolute right-2 text-indigo-500" 
                :title="isRecordingTrigger ? '点击结束录制' : '点击开始捕获按键'"
                @click="toggleTriggerRecording"
              >
                <MousePointer class="w-4 h-4" />
              </button>
            </div>

            <!-- Trigger Recording Pad (Supports Mouse & Keyboard) -->
            <div 
              class="key-record-box" 
              :class="{ recording: isRecordingTrigger, active: isTriggerBoxFocused }"
              tabindex="0"
              @focus="onTriggerBoxFocus"
              @blur="onTriggerBoxBlur"
              @keydown="onTriggerRecordKeyDown"
              @pointerdown="onTriggerRecordPointerDown"
              @contextmenu.prevent
            >
              <div v-if="remapModal.data.trigger && remapModal.data.trigger.length > 0" class="flex items-center gap-1.5 flex-wrap">
                <template v-for="(k, idx) in remapModal.data.trigger" :key="idx">
                  <span v-if="idx > 0" class="text-xs text-muted font-bold">+</span>
                  <span class="keycap" :class="{ mouse: isMouseKey(k) }">
                    {{ formatKeyLabel(k) }}
                  </span>
                </template>
                <span v-if="isRecordingTrigger" class="text-xs text-indigo-500 font-medium ml-2">
                  (录制中：可随时再次按下以覆盖重录，完成后点击上方“结束录制”)
                </span>
              </div>
              <div v-else-if="isRecordingTrigger" class="text-xs text-indigo-500 font-medium flex items-center gap-2">
                <span class="recording-dot"></span>
                <span>请按下鼠标侧键 (X1/X2/滚轮) 或键盘组合键...</span>
              </div>
              <div v-else class="text-xs text-muted flex items-center gap-2">
                <MousePointer class="w-3.5 h-3.5 text-indigo-400" />
                <span>点击“点击录制触发键”直接按键，或在上方输入框直接打字输入代码</span>
              </div>
            </div>

            <div class="modal-chips-row">
              <span class="text-xs text-muted">快速插入：</span>
              <button type="button" class="preset-tag" @click="insertTriggerKey('x1')">+ X1 侧键后退</button>
              <button type="button" class="preset-tag" @click="insertTriggerKey('x2')">+ X2 侧键前进</button>
              <button type="button" class="preset-tag" @click="insertTriggerKey('mbutton')">+ 滚轮中键</button>
              <button type="button" class="preset-tag" @click="insertTriggerKey('ctrl')">+ Ctrl</button>
              <button type="button" class="preset-tag" @click="insertTriggerKey('alt')">+ Alt</button>
              <button type="button" class="preset-tag" @click="insertTriggerKey('shift')">+ Shift</button>
              <button type="button" class="preset-tag" @click="insertTriggerKey('win')">+ Win</button>
            </div>
          </div>

          <!-- Output Section -->
          <div class="form-item col-span-2">
            <div class="flex items-center justify-between mb-1.5">
              <label class="form-label mb-0">输出按键 (Output - 支持录制与手动输入)</label>
              <div class="flex items-center gap-2">
                <span v-if="isRecordingOutput" class="badge-recording">
                  <span class="recording-dot"></span>
                  录制中 (系统热键已隔离)
                </span>
                <button 
                  type="button" 
                  class="btn btn-xs" 
                  :class="isRecordingOutput ? 'btn-danger' : 'btn-secondary'"
                  @click="toggleOutputRecording"
                >
                  {{ isRecordingOutput ? '⏹ 结束录制' : '⏺ 点击录制输出键' }}
                </button>
                <button 
                  v-if="remapModal.data.output && remapModal.data.output.length > 0" 
                  type="button" 
                  class="btn btn-xs btn-secondary" 
                  @click="remapModal.data.output = []"
                >
                  清空
                </button>
              </div>
            </div>

            <!-- Manual Editable Input Field for Output -->
            <div class="relative flex items-center mb-2">
              <input 
                type="text" 
                class="input-field font-mono text-sm pr-10" 
                placeholder="例如: ctrl+w 或 win+d (支持手动输入/修改代码，用 + 分隔)"
                :value="remapModal.data.output ? remapModal.data.output.join('+') : ''"
                @input="e => onRemapOutputTextInput(e.target.value)"
              />
              <button 
                type="button" 
                class="btn-icon absolute right-2 text-indigo-500" 
                :title="isRecordingOutput ? '点击结束录制' : '点击开始键盘录制'"
                @click="toggleOutputRecording"
              >
                <Keyboard class="w-4 h-4" />
              </button>
            </div>

            <!-- Output Recording Pad (Keyboard) -->
            <div 
              class="key-record-box" 
              :class="{ recording: isRecordingOutput, active: isOutputBoxFocused }"
              tabindex="0"
              @focus="onOutputBoxFocus"
              @blur="onOutputBoxBlur"
              @keydown="onOutputRecordKeyDown"
            >
              <div v-if="remapModal.data.output && remapModal.data.output.length > 0" class="flex items-center gap-1.5 flex-wrap">
                <template v-for="(k, idx) in remapModal.data.output" :key="idx">
                  <span v-if="idx > 0" class="text-xs text-muted font-bold">+</span>
                  <span class="keycap">
                    {{ formatKeyLabel(k) }}
                  </span>
                </template>
                <span v-if="isRecordingOutput" class="text-xs text-indigo-500 font-medium ml-2">
                  (录制中：可随时再次按下以覆盖重录，完成后点击上方“结束录制”)
                </span>
              </div>
              <div v-else-if="isRecordingOutput" class="text-xs text-indigo-500 font-medium flex items-center gap-2">
                <span class="recording-dot"></span>
                <span>请在键盘上按下目标组合键（例如按住 Ctrl + W）...</span>
              </div>
              <div v-else class="text-xs text-muted flex items-center gap-2">
                <Keyboard class="w-3.5 h-3.5 text-indigo-400" />
                <span>点击“点击录制输出键”直接按下组合键，或在上方输入框直接打字输入</span>
              </div>
            </div>

            <div class="modal-chips-row">
              <span class="text-xs text-muted">常用预设：</span>
              <button type="button" class="preset-tag" @click="remapModal.data.output = ['ctrl', 'w']">关闭标签 (Ctrl+W)</button>
              <button type="button" class="preset-tag" @click="remapModal.data.output = ['ctrl', 't']">新建标签 (Ctrl+T)</button>
              <button type="button" class="preset-tag" @click="remapModal.data.output = ['alt', 'left']">后退 (Alt+Left)</button>
              <button type="button" class="preset-tag" @click="remapModal.data.output = ['win', 'd']">显示桌面 (Win+D)</button>
              <button type="button" class="preset-tag" @click="remapModal.data.output = ['ctrl', 's']">保存 (Ctrl+S)</button>
            </div>
          </div>

          <div class="form-item col-span-2">
            <label class="form-label">描述</label>
            <input 
              type="text" 
              class="input-field" 
              placeholder="例如: 鼠标后退键关闭标签页"
              v-model="remapModal.data.description" 
            />
          </div>

          <div class="form-item col-span-2 flex items-center justify-between pt-1">
            <span class="font-medium text-sm text-main">启用该映射规则</span>
            <label class="toggle-switch">
              <input type="checkbox" v-model="remapModal.data.enabled" />
              <span class="slider"></span>
            </label>
          </div>
        </div>

        <div class="modal-footer">
          <button class="btn btn-secondary" @click="closeRemapModal">取消</button>
          <button class="btn btn-primary" @click="saveRemapModal">保存映射</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { getCurrentWindow } from '@tauri-apps/api/window'
import appIcon from './assets/icon.png'
import { 
  LayoutDashboard, 
  Keyboard, 
  MousePointer, 
  Cloud, 
  DownloadCloud, 
  Settings, 
  Sparkles,
  Edit,
  Trash2,
  Eye,
  EyeOff,
  Minus,
  Square,
  X,
  Sun,
  Moon,
  Palette,
  Monitor,
  Sliders,
  Folder,
  Activity,
  ShieldCheck,
  CheckCircle2,
  ArrowRight,
  ExternalLink,
  Server,
  RefreshCw,
  Upload,
  FolderOpen,
  Radio,
  Layers,
  Pin,
  LayoutGrid
} from '@lucide/vue'

const appWindow = getCurrentWindow()

const minimizeWindow = () => {
  appWindow.minimize()
}

const toggleMaximize = () => {
  appWindow.toggleMaximize()
}

const hideWindow = () => {
  appWindow.hide()
}

const toggleTheme = async () => {
  if (!config.value.app) return
  const current = config.value.app.theme || 'light'
  config.value.app.theme = current === 'slate' ? 'light' : 'slate'
  try {
    await invoke('update_config', { newConfig: config.value })
  } catch (err) {
    console.error('Failed to save theme:', err)
  }
}

const setTheme = async (themeName) => {
  if (!config.value.app) return
  config.value.app.theme = themeName
  try {
    await invoke('update_config', { newConfig: config.value })
    showToast(`已切换至${themeName === 'light' ? '浅色' : '深色'}主题`, 'success')
  } catch (err) {
    console.error('Failed to save theme:', err)
  }
}

const onHeaderMouseDown = async (e) => {
  if (e.button === 0 && !e.target.closest('button, input, select, label, .window-controls, .toggle-switch, .theme-toggle-btn')) {
    try {
      await appWindow.startDragging()
    } catch (err) {
      console.warn('startDragging error:', err)
    }
  }
}

const onHeaderDblClick = (e) => {
  if (!e.target.closest('button, input, select, label, .window-controls')) {
    appWindow.toggleMaximize()
  }
}

const currentTab = ref('overview')
const showPassword = ref(false)

// Sidebar Resizing State & Methods
const sidebarWidth = ref(Number(localStorage.getItem('bindx_sidebar_width')) || 215)
const isResizingSidebar = ref(false)

const startSidebarResize = (e) => {
  if (e.button !== 0) return
  e.preventDefault()
  isResizingSidebar.value = true
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'

  const onMouseMove = (moveEvent) => {
    let newWidth = moveEvent.clientX
    if (newWidth < 150) newWidth = 150
    if (newWidth > 360) newWidth = 360
    sidebarWidth.value = newWidth
  }

  const onMouseUp = () => {
    isResizingSidebar.value = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', onMouseUp)
    try {
      localStorage.setItem('bindx_sidebar_width', sidebarWidth.value.toString())
    } catch (err) {}
  }

  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}

const resetSidebarWidth = () => {
  sidebarWidth.value = 215
  try {
    localStorage.setItem('bindx_sidebar_width', '215')
  } catch (err) {}
}

const toast = ref({
  show: false,
  message: '',
  type: 'info'
})

const showToast = (message, type = 'info', duration = 3500) => {
  toast.value = { show: true, message, type }
  setTimeout(() => {
    toast.value.show = false
  }, duration)
}

const config = ref({
  app: {
    hotkey_running: true,
    mouse_running: false,
    autostart_enabled: true,
    font_preset: '常规',
    output_delay_ms: 20,
    restore_held_modifiers: true,
    theme: 'light'
  },
  hotkeys: {
    display_name: 'App Hotkey Manager',
    mutex_name: 'Global\\AppHotkeyManager',
    entries: []
  },
  mouse: {
    mappings: [],
    mouse_mappings: []
  },
  webdav: {
    server_url: '',
    username: '',
    password: '',
    remote_filename: 'bindx_config.json',
    auto_sync_on_startup: false
  },
  updater: {
    check_on_startup: true,
    update_url: 'https://api.github.com/repos/GOTOgxy/BindX/releases/latest'
  }
})

const activeHotkeysCount = computed(() => {
  return config.value.hotkeys.entries.filter(e => e.enabled).length
})

const navItems = [
  { id: 'overview', label: '概览', icon: LayoutDashboard },
  { id: 'hotkeys', label: '快捷键', icon: Keyboard },
  { id: 'remap', label: '按键映射', icon: MousePointer },
  { id: 'webdav', label: '云同步', icon: Cloud },
  { id: 'update', label: '版本更新', icon: DownloadCloud },
  { id: 'settings', label: '设置', icon: Settings },
]

// Fetch config from backend
const fetchConfig = async () => {
  try {
    const data = await invoke('get_config')
    if (data) {
      if (!data.app) data.app = {}
      if (!data.app.theme) data.app.theme = 'light'
      if (!data.mouse) data.mouse = { mappings: [], mouse_mappings: [] }
      if (!data.mouse.mappings) data.mouse.mappings = []
      config.value = data
    }
    await refreshConfigPathInfo()
  } catch (e) {
    showToast('加载配置失败: ' + e, 'danger')
  }
}

// Save all changes
const saveAll = async () => {
  try {
    await invoke('update_config', { newConfig: config.value })
    await refreshConfigPathInfo()
    showToast('设置已保存', 'success')
  } catch (e) {
    showToast('保存失败: ' + e, 'danger')
  }
}

// Engine Toggles
const onToggleHotkeyEngine = async () => {
  try {
    await invoke('toggle_hotkey_engine', { enable: config.value.app.hotkey_running })
    showToast(config.value.app.hotkey_running ? '快捷键监听已启动' : '快捷键监听已暂停', 'info')
  } catch (e) {
    showToast('切换快捷键服务失败: ' + e, 'danger')
  }
}

const onToggleMouseEngine = async () => {
  try {
    await invoke('toggle_mouse_engine', { enable: config.value.app.mouse_running })
    showToast(config.value.app.mouse_running ? '侧键监听已启动' : '侧键监听已停止', 'info')
  } catch (e) {
    showToast('切换侧键监听失败: ' + e, 'danger')
  }
}

// Format Helpers
const formatTargetType = (type) => {
  switch (type) {
    case 'browser_tab': return '网页标签'
    case 'builtin': return '内置应用'
    case 'win32':
    default: return '桌面客户端'
  }
}

const formatBehavior = (profile) => {
  if (!profile) return '普通呼出'
  const h = profile.hide_behavior || ''
  if (h.includes('tray')) return '托盘切换'
  if (h.includes('minimize')) return '最小化切换'
  return '窗口切换'
}

// Hotkey Modal
const hotkeyModal = ref({
  show: false,
  isEdit: false,
  index: -1,
  data: {}
})

const isRecordingHotkey = ref(false)
const isHotkeyBoxFocused = ref(false)

const toggleHotkeyRecording = async () => {
  isRecordingHotkey.value = !isRecordingHotkey.value
  try {
    await invoke('set_recording_state', { active: isRecordingHotkey.value })
  } catch (e) {
    console.error('set_recording_state error:', e)
  }
}

const onHotkeyBoxFocus = async () => {
  isHotkeyBoxFocused.value = true
  if (!isRecordingHotkey.value) {
    isRecordingHotkey.value = true
    try {
      await invoke('set_recording_state', { active: true })
    } catch (e) {}
  }
}

const onHotkeyBoxBlur = () => {
  isHotkeyBoxFocused.value = false
}

const onHotkeyInputFocus = async () => {
  if (isRecordingHotkey.value) {
    isRecordingHotkey.value = false
    try {
      await invoke('set_recording_state', { active: false })
    } catch (e) {}
  }
}

const closeHotkeyModal = async () => {
  if (isRecordingHotkey.value) {
    isRecordingHotkey.value = false
    try {
      await invoke('set_recording_state', { active: false })
    } catch (e) {}
  }
  hotkeyModal.value.show = false
}

const onHotkeyRecordKeyDown = (e) => {
  e.preventDefault()
  e.stopPropagation()

  const modifiers = []
  if (e.ctrlKey) modifiers.push('CTRL')
  if (e.altKey) modifiers.push('ALT')
  if (e.shiftKey) modifiers.push('SHIFT')
  if (e.metaKey) modifiers.push('WIN')

  let key = e.key.toUpperCase()

  // Wait if only modifier keys are pressed
  if (['CONTROL', 'ALT', 'SHIFT', 'META'].includes(key)) {
    return
  }

  // Normalizations for key labels
  if (key === ' ') key = 'SPACE'
  else if (key === 'ESCAPE') key = 'ESC'
  else if (key === 'ARROWUP') key = 'UP'
  else if (key === 'ARROWDOWN') key = 'DOWN'
  else if (key === 'ARROWLEFT') key = 'LEFT'
  else if (key === 'ARROWRIGHT') key = 'RIGHT'
  else if (key === 'BACKSPACE') key = 'BACKSPACE'
  else if (key === 'DELETE') key = 'DELETE'
  else if (key === 'ENTER') key = 'ENTER'
  else if (key === 'TAB') key = 'TAB'

  const all = [...modifiers]
  if (!all.includes(key)) {
    all.push(key)
  }

  if (all.length > 0) {
    hotkeyModal.value.data.hotkey = all.join('+')
    showToast(`已捕获按键: ${hotkeyModal.value.data.hotkey} (可继续按下重录，完成后点击“结束录制”)`, 'success')
  }
}

const browserPresetSelection = ref('auto')

const updateBrowserPresetSelectionFromData = () => {
  const exe = (hotkeyModal.value.data.exe_name || '').trim().toLowerCase()
  if (!exe) {
    browserPresetSelection.value = 'auto'
  } else if (exe === 'msedge.exe') {
    browserPresetSelection.value = 'msedge.exe'
  } else if (exe === 'chrome.exe') {
    browserPresetSelection.value = 'chrome.exe'
  } else {
    browserPresetSelection.value = 'custom'
  }
}

const onBrowserPresetChange = () => {
  if (browserPresetSelection.value === 'auto') {
    hotkeyModal.value.data.exe_name = ''
  } else if (browserPresetSelection.value === 'msedge.exe') {
    hotkeyModal.value.data.exe_name = 'msedge.exe'
  } else if (browserPresetSelection.value === 'chrome.exe') {
    hotkeyModal.value.data.exe_name = 'chrome.exe'
  } else if (browserPresetSelection.value === 'custom') {
    if (['msedge.exe', 'chrome.exe'].includes(hotkeyModal.value.data.exe_name?.toLowerCase())) {
      hotkeyModal.value.data.exe_name = ''
    }
  }
}

const onTargetTypeChange = (val) => {
  hotkeyModal.value.data.target_type = val
  if (val === 'browser_tab') {
    updateBrowserPresetSelectionFromData()
  }
}

const openAddHotkeyModal = () => {
  isRecordingHotkey.value = false
  isHotkeyBoxFocused.value = false
  hotkeyModal.value = {
    show: true,
    isEdit: false,
    index: -1,
    data: {
      app: '',
      name: '',
      hotkey: '',
      enabled: true,
      launch_if_not_running: true,
      install_path: '',
      target_type: 'win32',
      exe_name: '',
      title_keyword: '',
      _runtime_profile: {
        hide_behavior: 'minimize',
        show_behavior: 'activate_window'
      }
    }
  }
  updateBrowserPresetSelectionFromData()
}

const editHotkey = (entry, index) => {
  isRecordingHotkey.value = false
  isHotkeyBoxFocused.value = false
  const data = JSON.parse(JSON.stringify(entry))
  if (!data._runtime_profile) {
    data._runtime_profile = { hide_behavior: 'minimize' }
  } else if (!data._runtime_profile.hide_behavior) {
    data._runtime_profile.hide_behavior = 'minimize'
  }
  if (!data.target_type || data.target_type === 'builtin') {
    data.target_type = 'win32'
  }
  hotkeyModal.value = {
    show: true,
    isEdit: true,
    index,
    data
  }
  updateBrowserPresetSelectionFromData()
}

const applyHotkeyPreset = (preset) => {
  if (!hotkeyModal.value.data._runtime_profile) {
    hotkeyModal.value.data._runtime_profile = {}
  }
  switch (preset) {
    case 'bindx':
      hotkeyModal.value.data.app = 'bindx'
      hotkeyModal.value.data.name = 'BindX'
      hotkeyModal.value.data.target_type = 'win32'
      hotkeyModal.value.data.exe_name = 'bindx.exe'
      hotkeyModal.value.data.install_path = ''
      hotkeyModal.value.data.launch_if_not_running = false
      hotkeyModal.value.data._runtime_profile.hide_behavior = 'minimize'
      updateBrowserPresetSelectionFromData()
      showToast('已载入 BindX 自身窗口预设，请录制或输入专属唤起快捷键', 'info')
      break
    case 'cloudmusic':
      hotkeyModal.value.data.app = 'cloudmusic'
      hotkeyModal.value.data.name = '网易云音乐'
      hotkeyModal.value.data.target_type = 'win32'
      hotkeyModal.value.data.exe_name = 'cloudmusic.exe'
      hotkeyModal.value.data._runtime_profile.hide_behavior = 'tray'
      hotkeyModal.value.data.launch_if_not_running = true
      break
    case 'wechat':
      hotkeyModal.value.data.app = 'wechat'
      hotkeyModal.value.data.name = '微信'
      hotkeyModal.value.data.target_type = 'win32'
      hotkeyModal.value.data.exe_name = 'WeChat.exe'
      hotkeyModal.value.data._runtime_profile.hide_behavior = 'tray'
      hotkeyModal.value.data.launch_if_not_running = true
      break
    case 'termius':
      hotkeyModal.value.data.app = 'termius'
      hotkeyModal.value.data.name = 'Termius'
      hotkeyModal.value.data.target_type = 'win32'
      hotkeyModal.value.data.exe_name = 'Termius.exe'
      hotkeyModal.value.data._runtime_profile.hide_behavior = 'minimize'
      hotkeyModal.value.data.launch_if_not_running = true
      break
    case 'zotero':
      hotkeyModal.value.data.app = 'zotero'
      hotkeyModal.value.data.name = 'Zotero'
      hotkeyModal.value.data.target_type = 'win32'
      hotkeyModal.value.data.exe_name = 'zotero.exe'
      hotkeyModal.value.data._runtime_profile.hide_behavior = 'minimize'
      hotkeyModal.value.data.launch_if_not_running = true
      break
    case 'vscode':
      hotkeyModal.value.data.app = 'vscode'
      hotkeyModal.value.data.name = 'Visual Studio Code'
      hotkeyModal.value.data.target_type = 'win32'
      hotkeyModal.value.data.exe_name = 'Code.exe'
      hotkeyModal.value.data._runtime_profile.hide_behavior = 'minimize'
      hotkeyModal.value.data.launch_if_not_running = true
      break
    case 'terminal':
      hotkeyModal.value.data.app = 'terminal'
      hotkeyModal.value.data.name = 'Windows Terminal'
      hotkeyModal.value.data.target_type = 'win32'
      hotkeyModal.value.data.exe_name = 'wt.exe'
      hotkeyModal.value.data._runtime_profile.hide_behavior = 'minimize'
      hotkeyModal.value.data.launch_if_not_running = true
      break
    case 'browser_tab':
      hotkeyModal.value.data.target_type = 'browser_tab'
      hotkeyModal.value.data.name = hotkeyModal.value.data.name || '网页标签页'
      hotkeyModal.value.data.exe_name = ''
      hotkeyModal.value.data.title_keyword = hotkeyModal.value.data.title_keyword || '千问'
      hotkeyModal.value.data.install_path = ''
      hotkeyModal.value.data.launch_if_not_running = false
      hotkeyModal.value.data._runtime_profile.hide_behavior = 'minimize'
      updateBrowserPresetSelectionFromData()
      break
    default:
      hotkeyModal.value.data.target_type = 'win32'
      hotkeyModal.value.data._runtime_profile.hide_behavior = 'minimize'
      break
  }
}

const pickExecutableFile = async () => {
  try {
    const selected = await invoke('select_executable_file')
    if (selected) {
      hotkeyModal.value.data.install_path = selected
      const parts = selected.split(/\\|\//)
      const filename = parts.pop()
      if (filename) {
        if (!hotkeyModal.value.data.exe_name) {
          hotkeyModal.value.data.exe_name = filename
        }
        if (!hotkeyModal.value.data.name) {
          hotkeyModal.value.data.name = filename.replace(/\.exe$/i, '')
        }
        if (!hotkeyModal.value.data.app) {
          hotkeyModal.value.data.app = filename.replace(/\.exe$/i, '').toLowerCase()
        }
      }
      showToast('已选取程序文件', 'success')
    }
  } catch (err) {
    showToast('选择文件失败: ' + err, 'danger')
  }
}

const saveHotkeyModal = async () => {
  if (isRecordingHotkey.value) {
    isRecordingHotkey.value = false
    try {
      await invoke('set_recording_state', { active: false })
    } catch (e) {}
  }
  if (!hotkeyModal.value.data.hotkey || !hotkeyModal.value.data.hotkey.trim()) {
    showToast('快捷键组合不能为空，请录制或输入快捷键', 'danger')
    return
  }
  hotkeyModal.value.data.hotkey = hotkeyModal.value.data.hotkey
    .split('+')
    .map(k => k.trim().toUpperCase())
    .filter(Boolean)
    .join('+')

  if (!hotkeyModal.value.data.name?.trim()) {
    if (hotkeyModal.value.data.target_type === 'browser_tab' && hotkeyModal.value.data.title_keyword) {
      hotkeyModal.value.data.name = `网页: ${hotkeyModal.value.data.title_keyword}`
    } else if (hotkeyModal.value.data.exe_name) {
      hotkeyModal.value.data.name = hotkeyModal.value.data.exe_name.replace(/\.exe$/i, '')
    } else {
      hotkeyModal.value.data.name = '快捷键应用'
    }
  }
  if (!hotkeyModal.value.data.app) {
    hotkeyModal.value.data.app = hotkeyModal.value.data.name || 'app'
  }
  if (hotkeyModal.value.data.target_type === 'browser_tab') {
    if (browserPresetSelection.value === 'auto') {
      hotkeyModal.value.data.exe_name = ''
    }
    hotkeyModal.value.data.install_path = ''
    hotkeyModal.value.data.launch_if_not_running = false
  }
  if (hotkeyModal.value.isEdit) {
    config.value.hotkeys.entries[hotkeyModal.value.index] = hotkeyModal.value.data
  } else {
    config.value.hotkeys.entries.push(hotkeyModal.value.data)
  }
  hotkeyModal.value.show = false
  saveAll()
}

const deleteHotkey = (index) => {
  config.value.hotkeys.entries.splice(index, 1)
  saveAll()
}

// Key Detector & Unified Remap State
const isDetectingPadFocused = ref(false)
const detectedKeys = ref([])

// Key Helpers & Formatting
const isMouseKey = (k) => {
  if (!k || typeof k !== 'string') return false
  const lower = k.toLowerCase().trim()
  return ['x1', 'x2', 'mbutton', 'lbutton', 'rbutton'].includes(lower)
}

const formatKeyLabel = (k) => {
  if (!k || typeof k !== 'string') return ''
  const lower = k.toLowerCase().trim()
  switch (lower) {
    case 'x1': return '鼠标后退 (X1)'
    case 'x2': return '鼠标前进 (X2)'
    case 'mbutton': return '滚轮中键'
    case 'lbutton': return '鼠标左键'
    case 'rbutton': return '鼠标右键'
    case 'ctrl': return 'Ctrl'
    case 'alt': return 'Alt'
    case 'shift': return 'Shift'
    case 'win': return 'Win'
    case 'space': return 'Space'
    case 'esc': return 'Esc'
    case 'backspace': return 'Backspace'
    case 'delete': return 'Delete'
    case 'enter': return 'Enter'
    case 'tab': return 'Tab'
    case 'up': return '↑'
    case 'down': return '↓'
    case 'left': return '←'
    case 'right': return '→'
    default: return k.toUpperCase()
  }
}

const describeKeys = (keys) => {
  if (!keys || !Array.isArray(keys) || keys.length === 0) return '未命名操作'
  const labels = keys.map(k => formatKeyLabel(k))
  return `${labels.join('+')} 操作`
}

const getDetectedKeyDescription = (keys) => {
  if (!keys || !Array.isArray(keys) || keys.length === 0) return '无按键'
  const hasMouse = keys.some(isMouseKey)
  const hasModifier = keys.some(k => ['ctrl', 'alt', 'shift', 'win'].includes((k || '').toLowerCase()))
  if (hasMouse && hasModifier) return '鼠标与快捷键组合'
  if (hasMouse) return '鼠标按键'
  if (hasModifier && keys.length > 1) return '键盘组合快捷键'
  return '单键触发'
}

const clearDetectedKeys = () => {
  detectedKeys.value = []
}

const createMappingFromDetected = () => {
  if (!detectedKeys.value || detectedKeys.value.length === 0) return
  openAddRemapModal({
    trigger: [...detectedKeys.value],
    output: ['ctrl', 'w'],
    description: describeKeys(detectedKeys.value),
    enabled: true
  })
}

const onDetectorFocus = async () => {
  isDetectingPadFocused.value = true
  try {
    await invoke('set_recording_state', { active: true })
  } catch (e) {}
}

const onDetectorBlur = async () => {
  isDetectingPadFocused.value = false
  try {
    await invoke('set_recording_state', { active: false })
  } catch (e) {}
}

const onDetectorKeyDown = (e) => {
  e.preventDefault()
  e.stopPropagation()

  const modifiers = []
  if (e.ctrlKey) modifiers.push('ctrl')
  if (e.altKey) modifiers.push('alt')
  if (e.shiftKey) modifiers.push('shift')
  if (e.metaKey) modifiers.push('win')

  let key = e.key.toLowerCase()
  if (['control', 'alt', 'shift', 'meta'].includes(key)) {
    detectedKeys.value = [...modifiers]
    return
  }

  if (key === ' ') key = 'space'
  else if (key === 'escape') key = 'esc'
  else if (key === 'arrowup') key = 'up'
  else if (key === 'arrowdown') key = 'down'
  else if (key === 'arrowleft') key = 'left'
  else if (key === 'arrowright') key = 'right'

  const all = [...modifiers]
  if (!all.includes(key)) {
    all.push(key)
  }
  detectedKeys.value = all
}

const onDetectorPointerDown = (e) => {
  if (e.button === 3 || e.button === 4 || e.button === 1) {
    e.preventDefault()
    e.stopPropagation()
  } else {
    return
  }

  let mouseKey = ''
  if (e.button === 3) mouseKey = 'x1'
  else if (e.button === 4) mouseKey = 'x2'
  else if (e.button === 1) mouseKey = 'mbutton'

  const modifiers = []
  if (e.ctrlKey) modifiers.push('ctrl')
  if (e.altKey) modifiers.push('alt')
  if (e.shiftKey) modifiers.push('shift')
  if (e.metaKey) modifiers.push('win')

  const all = [...modifiers]
  if (!all.includes(mouseKey)) {
    all.push(mouseKey)
  }
  detectedKeys.value = all
}

const remapModal = ref({
  show: false,
  isEdit: false,
  index: -1,
  data: {
    trigger: [],
    output: [],
    description: '',
    enabled: true
  }
})

const isRecordingTrigger = ref(false)
const isTriggerBoxFocused = ref(false)
const isRecordingOutput = ref(false)
const isOutputBoxFocused = ref(false)

const closeRemapModal = async () => {
  if (isRecordingTrigger.value || isRecordingOutput.value) {
    isRecordingTrigger.value = false
    isRecordingOutput.value = false
    try {
      await invoke('set_recording_state', { active: false })
    } catch (e) {}
  }
  remapModal.value.show = false
}

const toggleTriggerRecording = async () => {
  isRecordingTrigger.value = !isRecordingTrigger.value
  isRecordingOutput.value = false
  try {
    await invoke('set_recording_state', { active: isRecordingTrigger.value })
  } catch (e) {}
}

const onTriggerBoxFocus = async () => {
  isTriggerBoxFocused.value = true
  if (!isRecordingTrigger.value) {
    isRecordingTrigger.value = true
    isRecordingOutput.value = false
    try {
      await invoke('set_recording_state', { active: true })
    } catch (e) {}
  }
}

const onTriggerBoxBlur = () => {
  isTriggerBoxFocused.value = false
}

const toggleOutputRecording = async () => {
  isRecordingOutput.value = !isRecordingOutput.value
  isRecordingTrigger.value = false
  try {
    await invoke('set_recording_state', { active: isRecordingOutput.value })
  } catch (e) {}
}

const onOutputBoxFocus = async () => {
  isOutputBoxFocused.value = true
  if (!isRecordingOutput.value) {
    isRecordingOutput.value = true
    isRecordingTrigger.value = false
    try {
      await invoke('set_recording_state', { active: true })
    } catch (e) {}
  }
}

const onOutputBoxBlur = () => {
  isOutputBoxFocused.value = false
}

const onRemapTriggerTextInput = (val) => {
  if (!val.trim()) {
    remapModal.value.data.trigger = []
    return
  }
  remapModal.value.data.trigger = val.split('+').map(s => s.trim().toLowerCase()).filter(Boolean)
}

const onRemapOutputTextInput = (val) => {
  if (!val.trim()) {
    remapModal.value.data.output = []
    return
  }
  remapModal.value.data.output = val.split('+').map(s => s.trim().toLowerCase()).filter(Boolean)
}

const onTriggerRecordKeyDown = (e) => {
  e.preventDefault()
  e.stopPropagation()

  const modifiers = []
  if (e.ctrlKey) modifiers.push('ctrl')
  if (e.altKey) modifiers.push('alt')
  if (e.shiftKey) modifiers.push('shift')
  if (e.metaKey) modifiers.push('win')

  let key = e.key.toLowerCase()
  if (['control', 'alt', 'shift', 'meta'].includes(key)) {
    return
  }

  if (key === ' ') key = 'space'
  else if (key === 'escape') key = 'esc'
  else if (key === 'arrowup') key = 'up'
  else if (key === 'arrowdown') key = 'down'
  else if (key === 'arrowleft') key = 'left'
  else if (key === 'arrowright') key = 'right'

  const all = [...modifiers]
  if (!all.includes(key)) {
    all.push(key)
  }
  remapModal.value.data.trigger = all
  if (!remapModal.value.data.description || remapModal.value.data.description === '鼠标侧键操作') {
    remapModal.value.data.description = describeKeys(all)
  }
  showToast(`已捕获触发按键: ${all.map(formatKeyLabel).join('+')} (可继续按下重录)`, 'success')
}

const onTriggerRecordPointerDown = (e) => {
  if (e.button === 3 || e.button === 4 || e.button === 1) {
    e.preventDefault()
    e.stopPropagation()
  } else {
    return
  }

  let mouseKey = ''
  if (e.button === 3) mouseKey = 'x1'
  else if (e.button === 4) mouseKey = 'x2'
  else if (e.button === 1) mouseKey = 'mbutton'

  const modifiers = []
  if (e.ctrlKey) modifiers.push('ctrl')
  if (e.altKey) modifiers.push('alt')
  if (e.shiftKey) modifiers.push('shift')
  if (e.metaKey) modifiers.push('win')

  const all = [...modifiers]
  if (!all.includes(mouseKey)) {
    all.push(mouseKey)
  }
  remapModal.value.data.trigger = all
  if (!remapModal.value.data.description || remapModal.value.data.description === '鼠标侧键操作') {
    remapModal.value.data.description = describeKeys(all)
  }
  showToast(`已捕获触发按键: ${all.map(formatKeyLabel).join('+')} (可继续按下重录)`, 'success')
}

const onOutputRecordKeyDown = (e) => {
  e.preventDefault()
  e.stopPropagation()

  const modifiers = []
  if (e.ctrlKey) modifiers.push('ctrl')
  if (e.altKey) modifiers.push('alt')
  if (e.shiftKey) modifiers.push('shift')
  if (e.metaKey) modifiers.push('win')

  let key = e.key.toLowerCase()
  if (['control', 'alt', 'shift', 'meta'].includes(key)) {
    return
  }

  if (key === ' ') key = 'space'
  else if (key === 'escape') key = 'esc'
  else if (key === 'arrowup') key = 'up'
  else if (key === 'arrowdown') key = 'down'
  else if (key === 'arrowleft') key = 'left'
  else if (key === 'arrowright') key = 'right'

  const all = [...modifiers]
  if (!all.includes(key)) {
    all.push(key)
  }
  remapModal.value.data.output = all
  showToast(`已捕获输出按键: ${all.map(formatKeyLabel).join('+')} (可继续按下重录)`, 'success')
}

const openAddRemapModal = (initialData = null) => {
  isRecordingTrigger.value = false
  isRecordingOutput.value = false
  isTriggerBoxFocused.value = false
  isOutputBoxFocused.value = false
  remapModal.value = {
    show: true,
    isEdit: false,
    index: -1,
    data: initialData ? { ...initialData } : {
      trigger: ['x1'],
      output: ['ctrl', 'w'],
      description: '鼠标侧键操作',
      enabled: true
    }
  }
}

const openEditRemapModal = (km, idx) => {
  isRecordingTrigger.value = false
  isRecordingOutput.value = false
  isTriggerBoxFocused.value = false
  isOutputBoxFocused.value = false
  remapModal.value = {
    show: true,
    isEdit: true,
    index: idx,
    data: JSON.parse(JSON.stringify(km))
  }
}

const insertTriggerKey = (k) => {
  if (!remapModal.value.data.trigger.includes(k)) {
    remapModal.value.data.trigger.push(k)
  }
}

const saveRemapModal = async () => {
  if (isRecordingTrigger.value || isRecordingOutput.value) {
    isRecordingTrigger.value = false
    isRecordingOutput.value = false
    try {
      await invoke('set_recording_state', { active: false })
    } catch (e) {}
  }
  if (!remapModal.value.data.trigger || remapModal.value.data.trigger.length === 0) {
    showToast('触发按键不能为空', 'danger')
    return
  }
  if (!remapModal.value.data.output || remapModal.value.data.output.length === 0) {
    showToast('输出按键不能为空', 'danger')
    return
  }
  if (remapModal.value.isEdit) {
    config.value.mouse.mappings[remapModal.value.index] = remapModal.value.data
  } else {
    config.value.mouse.mappings.push(remapModal.value.data)
  }
  remapModal.value.show = false
  saveAll()
}

const deleteKeyMapping = (index) => {
  config.value.mouse.mappings.splice(index, 1)
  saveAll()
}

const addQuickPreset = (trigger, output, desc) => {
  config.value.mouse.mappings.push({
    trigger: [...trigger],
    output: [...output],
    description: desc,
    enabled: true
  })
  saveAll()
  showToast(`已添加映射: ${formatKeyLabel(trigger[0])} → ${output.join('+').toUpperCase()}`, 'success')
}

// WebDAV Operations
const testingWebDav = ref(false)
const uploadingWebDav = ref(false)
const downloadingWebDav = ref(false)

const onTestWebDav = async () => {
  testingWebDav.value = true
  try {
    await invoke('update_config', { newConfig: config.value })
    await refreshConfigPathInfo()
    const res = await invoke('test_webdav', { config: config.value.webdav })
    showToast(res, 'success')
  } catch (e) {
    showToast('测试连接失败: ' + e, 'danger', 5000)
  } finally {
    testingWebDav.value = false
  }
}

const onUploadWebDav = async () => {
  uploadingWebDav.value = true
  try {
    const res = await invoke('upload_to_webdav', { config: config.value.webdav })
    showToast(res, 'success')
  } catch (e) {
    showToast('上传配置失败: ' + e, 'danger', 5000)
  } finally {
    uploadingWebDav.value = false
  }
}

const onDownloadWebDav = async () => {
  downloadingWebDav.value = true
  try {
    const currentWebDav = JSON.parse(JSON.stringify(config.value.webdav))
    const downloaded = await invoke('download_from_webdav', { config: config.value.webdav })
    // Preserve currently active WebDAV connection credentials
    if (currentWebDav && currentWebDav.server_url) {
      downloaded.webdav = currentWebDav
    }
    config.value = downloaded
    await refreshConfigPathInfo()
    showToast('配置同步成功，已保留当前云服务器连接设置', 'success')
  } catch (e) {
    showToast('同步失败: ' + e, 'danger', 5000)
  } finally {
    downloadingWebDav.value = false
  }
}

const applyWebDavPreset = (preset) => {
  if (preset === 'jianguoyun') {
    config.value.webdav.server_url = 'https://dav.jianguoyun.com/dav/'
    config.value.webdav.remote_filename = 'bindx'
    showToast('已载入坚果云地址模板', 'info')
  } else if (preset === 'alist') {
    config.value.webdav.server_url = 'http://127.0.0.1:5244/dav/'
    config.value.webdav.remote_filename = 'bindx'
    showToast('已载入 Alist 本地地址模板', 'info')
  } else if (preset === 'nextcloud') {
    config.value.webdav.server_url = 'https://your-cloud.com/remote.php/dav/files/USERNAME/'
    config.value.webdav.remote_filename = 'bindx'
    showToast('已载入 Nextcloud 模板', 'info')
  } else if (preset === 'custom') {
    config.value.webdav.server_url = ''
    config.value.webdav.username = ''
    config.value.webdav.password = ''
    config.value.webdav.remote_filename = 'bindx'
    showToast('已清空并重置为自定义 WebDAV 模板', 'info')
  }
}

// Updates
const checkingUpdate = ref(false)
const updateInfo = ref(null)

const onCheckUpdate = async () => {
  checkingUpdate.value = true
  try {
    const res = await invoke('check_software_update', { updateUrl: config.value.updater.update_url })
    updateInfo.value = res
    if (res.has_update) {
      showToast(`发现新版本 ${res.latest_version}`, 'success')
    } else {
      showToast('当前已是最新版本', 'info')
    }
  } catch (e) {
    showToast('检查更新失败: ' + e, 'danger', 5000)
  } finally {
    checkingUpdate.value = false
  }
}

const openUrl = async (url) => {
  try {
    await invoke('open_external_url', { url })
  } catch (e) {
    showToast('打开链接失败: ' + e, 'danger')
  }
}

const configPathInfo = ref({ full_path: '', dir_path: '', exists: false })

const refreshConfigPathInfo = async () => {
  try {
    const info = await invoke('get_config_path_info')
    if (info) {
      configPathInfo.value = info
    }
  } catch (e) {
    console.warn('获取配置文件路径失败:', e)
  }
}

const copyConfigPath = () => {
  if (!configPathInfo.value.full_path) return
  navigator.clipboard.writeText(configPathInfo.value.full_path)
    .then(() => showToast('配置文件路径已复制到剪贴板', 'info'))
    .catch(() => showToast(configPathInfo.value.full_path, 'info'))
}

const openDataFolder = async () => {
  try {
    await invoke('open_config_folder')
    await refreshConfigPathInfo()
    showToast('已在资源管理器中定位配置文件', 'success')
  } catch (e) {
    showToast('打开配置文件目录失败: ' + e, 'danger')
  }
}

const resolvedWebDavUrl = computed(() => {
  if (!config.value.webdav.server_url) return ''
  let base = config.value.webdav.server_url.trim().replace(/\/+$/, '')
  let dir = (config.value.webdav.remote_filename || '').trim().replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')
  if (!dir || dir === 'bindx_config.json') {
    return `${base}/bindx/`
  }
  if (dir.endsWith('/bindx_config.json')) {
    dir = dir.slice(0, -'/bindx_config.json'.length).replace(/^\/+|\/+$/g, '')
    return `${base}/${dir || 'bindx'}/`
  }
  return `${base}/${dir}/`
})

const remoteDirectory = computed(() => {
  let raw = (config.value.webdav?.remote_filename || '').trim().replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')
  if (!raw || raw === 'bindx_config.json') {
    return '/bindx/'
  }
  if (raw.endsWith('/bindx_config.json')) {
    raw = raw.slice(0, -'/bindx_config.json'.length).replace(/^\/+|\/+$/g, '')
    return raw ? `/${raw}/` : '/bindx/'
  }
  return `/${raw}/`
})

// Global hook for tray
window.navigateToTab = (tab) => {
  currentTab.value = tab
}

// Start Menu & Desktop Shortcut Operations
const isStartMenuPinned = ref(false)

const checkStartMenuStatus = async () => {
  try {
    isStartMenuPinned.value = await invoke('check_start_menu_status')
  } catch (err) {
    console.warn('check_start_menu_status error:', err)
  }
}

const onToggleStartMenu = async () => {
  try {
    const nextState = !isStartMenuPinned.value
    const res = await invoke('toggle_start_menu_shortcut', { enable: nextState })
    isStartMenuPinned.value = res
    if (res) {
      showToast('已成功添加到 Windows 开始菜单应用列表！您也可以点击“在文件夹定位”右键将其固定至磁贴', 'success', 5000)
    } else {
      showToast('已从 Windows 开始菜单移除', 'info')
    }
  } catch (err) {
    showToast('操作开始菜单失败: ' + err, 'danger')
  }
}

const onLocateStartMenu = async () => {
  try {
    await invoke('locate_start_menu_shortcut')
    isStartMenuPinned.value = true
    showToast('已在资源管理器中定位快捷方式，右键点击即可选择「固定到“开始”屏幕」', 'info', 5000)
  } catch (err) {
    showToast('打开开始菜单目录失败: ' + err, 'danger')
  }
}

const onCreateDesktop = async () => {
  try {
    await invoke('create_desktop_shortcut')
    showToast('已在桌面成功创建 BindX 快捷方式！', 'success')
  } catch (err) {
    showToast('创建桌面快捷方式失败: ' + err, 'danger')
  }
}

onMounted(() => {
  fetchConfig()
  checkStartMenuStatus()
})
</script>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  background: var(--bg-gradient);
  color: var(--text-main);
  transition: all 0.25s ease;
}

.app-header {
  height: 52px;
  background: var(--bg-header);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border-color);
  box-shadow: var(--header-shadow);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px 0 18px;
  flex-shrink: 0;
  user-select: none;
  -webkit-app-region: drag;
  cursor: default;
  transition: background 0.25s ease, border-color 0.25s ease;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  -webkit-app-region: drag;
}
.logo-box {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.95);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
  padding: 4px;
  -webkit-app-region: drag;
}
.brand-icon {
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}
.brand-text {
  display: flex;
  align-items: center;
  gap: 8px;
  -webkit-app-region: drag;
}
.brand-text .title {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.02em;
  background: linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  -webkit-app-region: drag;
  pointer-events: none;
}
[data-theme="slate"] .brand-text .title {
  background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.header-drag-spacer {
  flex: 1;
  height: 100%;
  min-width: 16px;
  -webkit-app-region: drag;
}

.header-status {
  display: flex;
  align-items: center;
  gap: 10px;
  -webkit-app-region: drag;
}

.status-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 12px;
  background: var(--pill-bg);
  border: 1px solid var(--pill-border);
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 500;
  color: var(--pill-text);
  -webkit-app-region: no-drag;
  transition: all 0.2s ease;
}
.status-pill.active {
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.35);
  color: #059669;
}
[data-theme="slate"] .status-pill.active {
  background: rgba(16, 185, 129, 0.15);
  border-color: rgba(16, 185, 129, 0.35);
  color: #34d399;
}
.status-pill .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #94a3b8;
}
.status-pill.active .dot {
  background: #10b981;
  box-shadow: 0 0 8px #10b981;
}

.badge-pill {
  font-size: 12px;
  font-weight: 500;
  padding: 5px 12px;
  border-radius: 9999px;
  background: var(--pill-bg);
  border: 1px solid var(--pill-border);
  color: var(--pill-text);
  -webkit-app-region: no-drag;
}
.badge-pill.enabled {
  color: #4f46e5;
  background: rgba(99, 102, 241, 0.12);
  border-color: rgba(99, 102, 241, 0.3);
}
[data-theme="slate"] .badge-pill.enabled {
  color: #818cf8;
  background: rgba(99, 102, 241, 0.18);
  border-color: rgba(99, 102, 241, 0.35);
}

.toggle-switch.mini {
  width: 30px;
  height: 18px;
}
.toggle-switch.mini .slider:before {
  width: 14px;
  height: 14px;
  left: 2px;
  bottom: 2px;
}
.toggle-switch.mini input:checked + .slider:before {
  transform: translateX(12px);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  -webkit-app-region: no-drag;
}

.theme-toggle-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 10px;
  border-radius: 8px;
  background: var(--pill-bg);
  border: 1px solid var(--pill-border);
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.18s ease;
  -webkit-app-region: no-drag;
}
.theme-toggle-btn:hover {
  background: var(--btn-sec-hover);
  border-color: var(--border-hover);
}

.window-controls {
  display: flex;
  align-items: center;
  gap: 3px;
  -webkit-app-region: no-drag;
}
.win-btn {
  width: 36px;
  height: 32px;
  border-radius: 7px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
  -webkit-app-region: no-drag;
}
.win-btn:hover {
  background: var(--btn-sec-hover);
  color: var(--text-main);
}
.win-close:hover {
  background: #ef4444 !important;
  color: #ffffff !important;
}

.version-tag {
  font-size: 11px;
  padding: 2px 8px;
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(99, 102, 241, 0.25);
  color: #4f46e5;
  border-radius: 9999px;
  font-weight: 600;
  -webkit-app-region: drag;
  pointer-events: none;
}
[data-theme="slate"] .version-tag {
  background: rgba(56, 189, 248, 0.15);
  border-color: rgba(56, 189, 248, 0.3);
  color: #38bdf8;
}

.app-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.sidebar {
  min-width: 150px;
  max-width: 360px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  padding: 16px 10px;
  flex-shrink: 0;
  gap: 4px;
  transition: background 0.25s ease, border-color 0.25s ease;
  overflow-x: hidden;
  overflow-y: auto;
  position: relative;
  user-select: none;
}

/* Draggable Splitter Handle */
.sidebar-resizer {
  width: 10px;
  margin-left: -5px;
  margin-right: -5px;
  z-index: 25;
  cursor: col-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  user-select: none;
  touch-action: none;
}

.resizer-line {
  width: 2px;
  height: 100%;
  background: transparent;
  border-radius: 1px;
  transition: background 0.15s ease, width 0.15s ease;
}

.sidebar-resizer:hover .resizer-line,
.sidebar-resizer.resizing .resizer-line {
  background: #6366f1;
  width: 3px;
  box-shadow: 0 0 8px rgba(99, 102, 241, 0.4);
}

[data-theme="slate"] .sidebar-resizer:hover .resizer-line,
[data-theme="slate"] .sidebar-resizer.resizing .resizer-line {
  background: #38bdf8;
  box-shadow: 0 0 8px rgba(56, 189, 248, 0.4);
}

.nav-tab {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 11px 14px;
  border-radius: 10px;
  font-size: 13.5px;
  font-weight: 500;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all 0.16s ease;
  position: relative;
  white-space: nowrap;
  overflow: hidden;
}
.tab-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.nav-tab:hover {
  background: var(--bg-card-subtle);
  color: var(--text-main);
}
.nav-tab.active {
  background: rgba(99, 102, 241, 0.12);
  color: #4f46e5;
  font-weight: 600;
}
[data-theme="slate"] .nav-tab.active {
  background: rgba(99, 102, 241, 0.22);
  color: #38bdf8;
}
.tab-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.sidebar-footer {
  margin-top: auto;
  padding-top: 14px;
  border-top: 1px solid var(--border-color);
}
.cloud-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.18s ease;
  box-shadow: var(--card-shadow);
}
.cloud-indicator:hover {
  border-color: var(--border-hover);
  background: var(--bg-card-hover);
  transform: translateY(-1px);
}
.indicator-icon-wrap {
  width: 28px;
  height: 28px;
  border-radius: 7px;
  background: rgba(6, 182, 212, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.indicator-icon {
  color: #06b6d4;
}
.indicator-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow: hidden;
}
.indicator-info .label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-main);
}
.indicator-info .val-row {
  display: flex;
  align-items: center;
  gap: 5px;
}
.indicator-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.indicator-dot.online {
  background: #10b981;
}
.indicator-dot.offline {
  background: #94a3b8;
}
.indicator-info .val {
  font-size: 11px;
  color: var(--text-muted);
}

.content-panel {
  flex: 1;
  overflow-y: auto;
  padding: 28px 36px;
  position: relative;
}

.pane-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 24px;
}
.pane-header h2 {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-main);
  letter-spacing: -0.02em;
}
.pane-header .subtitle {
  font-size: 13.5px;
  color: var(--text-muted);
  margin-top: 4px;
  line-height: 1.5;
}
.pane-header .actions {
  display: flex;
  gap: 10px;
}

/* KPI Row & Cards */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.kpi-card {
  padding: 18px 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  border-radius: 14px;
}
.kpi-icon-wrap {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.hotkey-accent {
  background: rgba(99, 102, 241, 0.12);
}
.remap-accent {
  background: rgba(236, 72, 153, 0.12);
}
.cloud-accent {
  background: rgba(6, 182, 212, 0.12);
}
.kpi-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow: hidden;
}
.kpi-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}
.kpi-value-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}
.kpi-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-main);
  letter-spacing: -0.02em;
}
.kpi-unit {
  font-size: 12px;
  color: var(--text-muted);
}
.kpi-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.kpi-status-dot.online {
  background: #10b981;
  box-shadow: 0 0 8px #10b981;
}
.kpi-status-dot.offline {
  background: #94a3b8;
}
.kpi-text-val {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-main);
}

/* Grid & Cards */
.grid-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 20px;
}

/* Integration Cards (Bottom Overview) */
.integration-card {
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  border-radius: 14px;
}
.integration-header {
  display: flex;
  align-items: center;
  gap: 14px;
}
.integration-icon-wrap {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.cloud-wrap {
  background: rgba(6, 182, 212, 0.12);
}
.update-wrap {
  background: rgba(99, 102, 241, 0.12);
}
.integration-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-main);
}
.integration-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}
.integration-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  padding: 12px 16px;
  background: var(--bg-card-subtle);
  border-radius: 10px;
  border: 1px solid var(--border-color);
}
.meta-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  overflow: hidden;
}
.meta-label {
  font-size: 11.5px;
  color: var(--text-muted);
}
.meta-val {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-main);
  text-overflow: ellipsis;
  overflow: hidden;
  white-space: nowrap;
}
.integration-actions {
  display: flex;
  gap: 10px;
  margin-top: auto;
}

.engine-card {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  border-radius: 14px;
}
.engine-card .card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.card-icon-title {
  display: flex;
  align-items: center;
  gap: 14px;
}
.engine-avatar {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 14px rgba(0,0,0,0.18);
  flex-shrink: 0;
}
.hotkey-grad {
  background: linear-gradient(135deg, #0284c7 0%, #6366f1 100%);
}
.mouse-grad {
  background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%);
}
.card-icon-title h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-main);
}
.card-icon-title p {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}

.stat-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  font-size: 13.5px;
  border-bottom: 1px solid var(--border-color);
}
.stat-name {
  color: var(--text-secondary);
}
.stat-value {
  color: var(--text-main);
  font-weight: 600;
}
.status-tag {
  font-size: 12px;
  font-weight: 500;
  padding: 3px 10px;
  border-radius: 9999px;
}
.status-tag.online {
  background: rgba(16, 185, 129, 0.12);
  color: #059669;
}
[data-theme="slate"] .status-tag.online {
  background: rgba(16, 185, 129, 0.18);
  color: #34d399;
}
.status-tag.offline {
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}

/* Data Table */
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13.5px;
}
.data-table th {
  background: var(--bg-card-subtle);
  padding: 13px 18px;
  text-align: left;
  font-weight: 600;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-color);
  letter-spacing: 0.02em;
}
.data-table td {
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-primary);
  vertical-align: middle;
}
.data-table tr:hover td {
  background: var(--bg-card-subtle);
}

.type-pill {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 6px;
  font-weight: 600;
}
.type-pill.browser_tab {
  background: rgba(6, 182, 212, 0.12);
  color: #0891b2;
}
[data-theme="slate"] .type-pill.browser_tab {
  background: rgba(56, 189, 248, 0.15);
  color: #38bdf8;
}
.type-pill.builtin {
  background: rgba(168, 85, 247, 0.12);
  color: #9333ea;
}
[data-theme="slate"] .type-pill.builtin {
  background: rgba(168, 85, 247, 0.18);
  color: #c084fc;
}
.type-pill.win32 {
  background: rgba(99, 102, 241, 0.12);
  color: #4f46e5;
}
[data-theme="slate"] .type-pill.win32 {
  background: rgba(99, 102, 241, 0.18);
  color: #818cf8;
}

.table-actions {
  display: flex;
  gap: 8px;
}
.btn-icon {
  background: transparent;
  border: none;
  color: var(--text-muted);
  padding: 6px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}
.btn-icon:hover {
  background: var(--btn-sec-hover);
  color: var(--text-main);
}
.btn-icon.danger:hover {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

/* Forms */
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
.col-span-2 {
  grid-column: span 2;
}
.form-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 7px;
}
.field-hint {
  display: block;
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--text-muted);
  margin-top: 6px;
}
.field-hint code {
  background: var(--bg-card-subtle);
  padding: 2px 5px;
  border-radius: 4px;
  font-size: 12px;
  border: 1px solid var(--border-color);
}

/* Remap Section & Mouse Cards */
.remap-section-card {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  border-radius: 14px;
}
.section-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.section-icon-wrap {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.mouse-wrap {
  background: rgba(236, 72, 153, 0.12);
}
.key-wrap {
  background: rgba(99, 102, 241, 0.12);
}
.webdav-blue {
  background: rgba(99, 102, 241, 0.12);
}
.cloud-blue {
  background: rgba(6, 182, 212, 0.12);
}
.theme-wrap {
  background: rgba(99, 102, 241, 0.12);
}
.system-wrap {
  background: rgba(6, 182, 212, 0.12);
}
.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-main);
}
.section-desc {
  font-size: 12.5px;
  color: var(--text-muted);
  margin-top: 3px;
}
.engine-badge-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 12px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 500;
  background: var(--pill-bg);
  border: 1px solid var(--pill-border);
  color: var(--pill-text);
}
.engine-badge-pill.active {
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.35);
  color: #059669;
}
[data-theme="slate"] .engine-badge-pill.active {
  background: rgba(16, 185, 129, 0.18);
  border-color: rgba(16, 185, 129, 0.4);
  color: #34d399;
}
.engine-badge-pill .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #94a3b8;
}
.engine-badge-pill.active .dot {
  background: #10b981;
  box-shadow: 0 0 6px #10b981;
}

/* Key Detector & Pad */
.detector-card {
  padding: 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  border-radius: 14px;
}
.detector-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.section-icon-wrap.detector-wrap {
  background: rgba(99, 102, 241, 0.12);
}
.detector-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.detector-pad {
  padding: 26px 20px;
  background: var(--bg-card-subtle);
  border: 2px dashed var(--border-color);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 110px;
  cursor: pointer;
  outline: none;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  user-select: none;
}
.detector-pad:hover {
  border-color: var(--border-hover);
  background: var(--bg-card);
}
.detector-pad.active, .detector-pad:focus {
  border-color: #6366f1;
  background: rgba(99, 102, 241, 0.04);
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.15);
}
.detector-idle {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  text-align: center;
}
.detector-hint-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}
.detector-hint-sub {
  font-size: 12px;
  color: var(--text-muted);
}
.detected-keys-display {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.detector-plus {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-muted);
}
.keycap.detector-keycap {
  font-size: 14.5px;
  padding: 8px 16px;
  border-radius: 9px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}
.keycap.mouse {
  background: rgba(236, 72, 153, 0.12);
  color: #db2777;
  border-color: rgba(236, 72, 153, 0.35);
}
[data-theme="slate"] .keycap.mouse {
  background: rgba(236, 72, 153, 0.22);
  color: #f472b6;
  border-color: rgba(236, 72, 153, 0.45);
}
.detected-sub-info {
  display: flex;
  align-items: center;
  gap: 10px;
}
.detector-tag {
  font-size: 11.5px;
  font-weight: 600;
  padding: 2px 8px;
  background: rgba(99, 102, 241, 0.12);
  color: #4f46e5;
  border-radius: 6px;
}
[data-theme="slate"] .detector-tag {
  background: rgba(99, 102, 241, 0.25);
  color: #818cf8;
}
.detector-presets {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding-top: 4px;
}
.modal-chips-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

/* Key Recording Pad & Badges */
.key-record-box {
  min-height: 44px;
  padding: 8px 14px;
  background: var(--bg-card-subtle);
  border: 1.5px dashed var(--border-color);
  border-radius: 9px;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  outline: none;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  user-select: none;
}
.key-record-box:hover {
  border-color: var(--border-hover);
  background: var(--bg-card);
}
.key-record-box.active, .key-record-box:focus {
  border-color: #6366f1;
  background: rgba(99, 102, 241, 0.05);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.18);
  border-style: solid;
}
.key-record-box.recording {
  border-color: #ef4444;
  background: rgba(239, 68, 68, 0.05);
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.18);
  border-style: solid;
}
.badge-recording {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  font-weight: 600;
  color: #ef4444;
  background: rgba(239, 68, 68, 0.12);
  padding: 2px 9px;
  border-radius: 9999px;
  border: 1px solid rgba(239, 68, 68, 0.25);
}
[data-theme="slate"] .badge-recording {
  color: #f87171;
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.35);
}
.recording-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #ef4444;
  animation: pulse-dot 1.2s infinite ease-in-out;
}
[data-theme="slate"] .recording-dot {
  background: #f87171;
}
@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.35; transform: scale(0.75); }
}
.btn-xs {
  font-size: 11.5px !important;
  padding: 4px 10px !important;
  border-radius: 6px !important;
  height: auto !important;
  min-height: 26px !important;
}
.btn-danger {
  background: #ef4444 !important;
  color: #ffffff !important;
  border: none !important;
}
.btn-danger:hover {
  background: #dc2626 !important;
}

.keycap.accent {
  background: rgba(99, 102, 241, 0.12);
  color: #4f46e5;
  border-color: rgba(99, 102, 241, 0.3);
}
[data-theme="slate"] .keycap.accent {
  background: rgba(99, 102, 241, 0.22);
  color: #818cf8;
  border-color: rgba(99, 102, 241, 0.4);
}
.preset-tag {
  font-size: 11px;
  font-weight: 500;
  padding: 3px 8px;
  border-radius: 6px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
}
.preset-tag:hover {
  background: var(--btn-sec-hover);
  color: var(--text-main);
  border-color: var(--border-hover);
}

/* WebDAV Dashboard Layout */
.webdav-dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}
.webdav-card {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  border-radius: 14px;
  min-width: 0;
}
.preset-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}
.preset-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}
.preset-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.preset-chip {
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 500;
  border-radius: 8px;
  background: var(--bg-card-subtle);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.15s ease;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.preset-chip:hover {
  background: var(--btn-sec-hover);
  border-color: var(--border-hover);
  transform: translateY(-1px);
}
.preset-chip.active {
  background: rgba(99, 102, 241, 0.12);
  border-color: #6366f1;
  color: #4f46e5;
  font-weight: 600;
}
[data-theme="slate"] .preset-chip.active {
  background: rgba(99, 102, 241, 0.22);
  border-color: #818cf8;
  color: #38bdf8;
}
.preset-chip-primary {
  background: rgba(99, 102, 241, 0.12) !important;
  color: #4f46e5 !important;
  border-color: rgba(99, 102, 241, 0.35) !important;
  font-weight: 600 !important;
}
[data-theme="slate"] .preset-chip-primary {
  background: rgba(99, 102, 241, 0.22) !important;
  color: #818cf8 !important;
  border-color: rgba(99, 102, 241, 0.5) !important;
}
.preset-star {
  color: #eab308;
}
.card-footer-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}
.sync-status-box {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
  background: var(--bg-card-subtle);
  border-radius: 10px;
  border: 1px solid var(--border-color);
  min-width: 0;
}
.sync-status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12.5px;
  gap: 12px;
  min-width: 0;
}
.sync-label {
  color: var(--text-secondary);
  font-weight: 500;
  flex-shrink: 0;
}
.sync-value {
  min-width: 0;
  text-align: right;
}
.sync-actions-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.sync-action-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: var(--bg-card-subtle);
  border-radius: 10px;
  border: 1px solid var(--border-color);
  transition: all 0.15s ease;
  gap: 14px;
}
.sync-action-item:hover {
  background: var(--bg-card);
  border-color: var(--border-hover);
}
.sync-action-item.highlight {
  background: rgba(99, 102, 241, 0.06);
  border-color: rgba(99, 102, 241, 0.25);
}
.sync-action-desc {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.sync-action-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-main);
}
.sync-action-sub {
  font-size: 11.5px;
  color: var(--text-muted);
}

/* Update Dashboard Layout */
.update-dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}
.version-hero-card {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  border-radius: 14px;
  min-width: 0;
}
.hero-header-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}
.hero-icon-box {
  width: 50px;
  height: 50px;
  border-radius: 14px;
  background: linear-gradient(135deg, #06b6d4 0%, #4f46e5 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
  flex-shrink: 0;
}
.hero-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-main);
}
.hero-ver {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 2px;
}
.hero-specs-list {
  display: flex;
  flex-direction: column;
  gap: 9px;
  padding: 14px 16px;
  background: var(--bg-card-subtle);
  border-radius: 10px;
  border: 1px solid var(--border-color);
}
.spec-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12.5px;
}
.spec-name {
  color: var(--text-secondary);
  font-weight: 500;
}
.spec-val {
  color: var(--text-main);
  font-weight: 600;
}
.arch-cards-panel {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  border-radius: 14px;
}
.arch-tiles-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.arch-tile {
  display: flex;
  gap: 14px;
  padding: 14px 16px;
  background: var(--bg-card-subtle);
  border-radius: 10px;
  border: 1px solid var(--border-color);
  transition: all 0.15s ease;
}
.arch-tile:hover {
  background: var(--bg-card);
  border-color: var(--border-hover);
  transform: translateY(-1px);
}
.arch-icon {
  font-size: 20px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.arch-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-main);
}
.arch-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
  line-height: 1.5;
}

/* Settings Section & Fluent Tiles */
.settings-section-card {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  border-radius: 14px;
}
.theme-options-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.theme-card-option {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 20px;
  background: var(--bg-card-subtle);
  border: 2px solid var(--border-color);
  border-radius: 12px;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s ease;
}
.theme-card-option:hover {
  border-color: var(--border-hover);
  background: var(--bg-card);
}
.theme-card-option.active {
  border-color: #4f46e5;
  background: var(--bg-card);
  box-shadow: 0 0 0 1px #4f46e5, var(--card-shadow);
}
[data-theme="slate"] .theme-card-option.active {
  border-color: #6366f1;
  box-shadow: 0 0 0 1px #6366f1, var(--card-shadow);
}
.theme-preview {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.light-preview {
  background: #ffffff;
  border: 1px solid #cbd5e1;
  box-shadow: 0 2px 6px rgba(0,0,0,0.06);
}
.slate-preview {
  background: #1e293b;
  border: 1px solid rgba(255,255,255,0.12);
  box-shadow: 0 2px 6px rgba(0,0,0,0.3);
}
.theme-meta .name {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}
.theme-meta .desc {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}
.theme-check {
  margin-left: auto;
}
.settings-tiles-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.setting-tile {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: var(--bg-card-subtle);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  transition: all 0.18s ease;
}
.setting-tile:hover {
  background: var(--bg-card);
  border-color: var(--border-hover);
  box-shadow: var(--card-shadow);
}
.tile-icon-box {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.autostart-box {
  background: rgba(99, 102, 241, 0.12);
}
.keyboard-box {
  background: rgba(6, 182, 212, 0.12);
}
.slider-box {
  background: rgba(168, 85, 247, 0.12);
}
.folder-box {
  background: rgba(16, 185, 129, 0.12);
}
.start-box {
  background: rgba(99, 102, 241, 0.12);
}
.desktop-box {
  background: rgba(6, 182, 212, 0.12);
}
.tile-content {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex: 1;
}
.tile-title {
  font-size: 14.5px;
  font-weight: 600;
  color: var(--text-main);
}
.tile-desc {
  font-size: 12.5px;
  color: var(--text-muted);
  line-height: 1.45;
}
.tile-action {
  flex-shrink: 0;
}
.tile-action-slider {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-shrink: 0;
  min-width: 200px;
}
.slider-badge {
  font-family: monospace;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 6px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  color: #4f46e5;
  min-width: 56px;
  text-align: center;
}
[data-theme="slate"] .slider-badge {
  color: #38bdf8;
}
.range-slider {
  flex: 1;
  accent-color: #4f46e5;
  cursor: pointer;
}
.tile-action-path {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.path-badge {
  font-family: monospace;
  font-size: 11px;
  padding: 6px 12px;
  border-radius: 8px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  user-select: all;
  cursor: pointer;
  transition: all 0.2s ease;
}
.path-badge:hover {
  border-color: var(--primary);
  color: var(--primary);
}
.tile-action-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.status-tag.mini {
  font-size: 11px;
  padding: 1.5px 8px;
  border-radius: 9999px;
  font-weight: 500;
}

/* Toast */
.toast-banner {
  position: absolute;
  top: 18px;
  right: 28px;
  z-index: 100;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 18px;
  border-radius: 10px;
  font-size: 13.5px;
  box-shadow: 0 12px 30px rgba(0,0,0,0.18);
  backdrop-filter: blur(14px);
}
.toast-banner.success {
  background: rgba(16, 185, 129, 0.95);
  border: 1px solid #059669;
  color: #ffffff;
}
.toast-banner.danger {
  background: rgba(239, 68, 68, 0.95);
  border: 1px solid #dc2626;
  color: #ffffff;
}
.toast-banner.info {
  background: rgba(79, 70, 229, 0.95);
  border: 1px solid #4338ca;
  color: #ffffff;
}
.toast-close {
  background: transparent;
  border: none;
  color: inherit;
  font-size: 18px;
  cursor: pointer;
}

/* Update Tab Elements */
.update-badge {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 9999px;
  font-weight: 600;
}
.update-badge.has-update {
  background: rgba(245, 158, 11, 0.15);
  color: #d97706;
  border: 1px solid rgba(245, 158, 11, 0.35);
}
.update-badge.latest {
  background: rgba(16, 185, 129, 0.15);
  color: #059669;
  border: 1px solid rgba(16, 185, 129, 0.35);
}

.changelog-box {
  background: var(--bg-card-subtle);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 14px;
  max-height: 220px;
  overflow-y: auto;
}
.changelog-text {
  font-family: inherit;
  font-size: 12.5px;
  color: var(--text-primary);
  white-space: pre-wrap;
  line-height: 1.65;
}

.distribution-tip {
  margin-top: 14px;
  padding: 14px 16px;
  border-radius: 10px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.2);
}

/* Modals */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.65);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  padding: 16px;
}
.modal-dialog {
  width: 540px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 36px);
  display: flex;
  flex-direction: column;
  padding: 24px;
  overflow: hidden;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-shrink: 0;
}
.modal-header h3 {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-main);
}
.modal-close {
  background: transparent;
  border: none;
  font-size: 22px;
  color: var(--text-muted);
  cursor: pointer;
}
.modal-close:hover {
  color: var(--text-main);
}
.modal-body {
  overflow-y: auto;
  flex: 1;
  min-height: 0;
  padding-right: 6px;
  margin-right: -4px;
}
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
  flex-shrink: 0;
}

.password-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
}
.password-input {
  padding-right: 42px !important;
}
.eye-btn {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  background: transparent !important;
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
  color: var(--text-muted);
  padding: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.15s ease;
}
.eye-btn:hover {
  color: var(--text-main);
  background: var(--btn-sec-hover) !important;
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
