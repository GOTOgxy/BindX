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
          <span class="version-tag" data-tauri-drag-region>v2.0</span>
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
      <nav class="sidebar">
        <button 
          v-for="item in navItems" 
          :key="item.id"
          class="nav-tab" 
          :class="{ active: currentTab === item.id }"
          @click="currentTab = item.id"
        >
          <component :is="item.icon" class="tab-icon" />
          <span>{{ item.label }}</span>
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
                <span class="kpi-label">按键与侧键映射</span>
                <div class="kpi-value-row">
                  <span class="kpi-value">{{ config.mouse.mouse_mappings.length + config.mouse.mappings.length }}</span>
                  <span class="kpi-unit">项</span>
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
                    <h3>输入映射</h3>
                    <p>鼠标侧键与键盘组合键分派</p>
                  </div>
                </div>
                <label class="toggle-switch">
                  <input type="checkbox" v-model="config.app.mouse_running" @change="onToggleMouseEngine" />
                  <span class="slider"></span>
                </label>
              </div>

              <div class="card-body">
                <div class="stat-row">
                  <span class="stat-name">鼠标侧键</span>
                  <span class="stat-value">{{ config.mouse.mouse_mappings.length }} 项</span>
                </div>
                <div class="stat-row">
                  <span class="stat-name">组合键映射</span>
                  <span class="stat-value">{{ config.mouse.mappings.length }} 项</span>
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
                  <span class="meta-val font-mono text-indigo-600 font-semibold">v2.0.0</span>
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

          <!-- Section 1: Mouse Side Buttons Card -->
          <div class="glass-panel remap-section-card">
            <div class="section-card-header">
              <div class="card-icon-title">
                <div class="section-icon-wrap mouse-wrap">
                  <MousePointer class="w-5 h-5 text-pink-500" />
                </div>
                <div>
                  <h3 class="section-title">鼠标侧键</h3>
                  <p class="section-desc">将鼠标侧键映射为指定快捷键操作</p>
                </div>
              </div>
              <div class="engine-badge-pill" :class="{ active: config.app.mouse_running }">
                <span class="dot"></span>
                <span>侧键监听: {{ config.app.mouse_running ? '运行中' : '已暂停' }}</span>
              </div>
            </div>

            <div class="mouse-cards-grid">
              <div 
                v-for="(m, idx) in config.mouse.mouse_mappings" 
                :key="idx" 
                class="mouse-tile-card"
              >
                <div class="mouse-tile-top">
                  <div class="mouse-badge-group">
                    <span class="keycap mouse-keycap">{{ m.button.toUpperCase() }}</span>
                    <div>
                      <span class="mouse-btn-name">{{ m.button.toUpperCase() === 'X1' ? '后退键' : '前进键' }}</span>
                      <span class="mouse-btn-desc">{{ m.description || (m.button.toUpperCase() === 'X1' ? '关闭标签页' : '前进') }}</span>
                    </div>
                  </div>
                  <label class="toggle-switch">
                    <input type="checkbox" v-model="m.enabled" @change="saveAll" />
                    <span class="slider"></span>
                  </label>
                </div>

                <div class="mouse-mapping-flow">
                  <div class="flow-step">
                    <span class="flow-label">触发键</span>
                    <span class="keycap">{{ m.button.toUpperCase() }}</span>
                  </div>
                  <div class="flow-arrow">
                    <ArrowRight class="w-4 h-4 text-slate-400" />
                  </div>
                  <div class="flow-step">
                    <span class="flow-label">输出键</span>
                    <div class="flex gap-1.5 flex-wrap">
                      <span v-for="k in m.output" :key="k" class="keycap accent">{{ k.toUpperCase() }}</span>
                    </div>
                  </div>
                </div>

                <div class="mouse-input-row">
                  <input 
                    type="text" 
                    class="input-field mouse-input" 
                    placeholder="例如 ctrl w"
                    :value="m.output.join(' ')"
                    @change="e => updateMouseOutput(m, e.target.value)"
                  />
                </div>

                <!-- Quick Presets -->
                <div class="quick-presets">
                  <span class="preset-hint">常用预设：</span>
                  <button type="button" class="preset-tag" @click="setMousePreset(m, ['ctrl', 'w'])">关闭标签 (Ctrl+W)</button>
                  <button type="button" class="preset-tag" @click="setMousePreset(m, ['ctrl', 't'])">新建标签 (Ctrl+T)</button>
                  <button type="button" class="preset-tag" @click="setMousePreset(m, ['alt', 'left'])">后退 (Alt+Left)</button>
                  <button type="button" class="preset-tag" @click="setMousePreset(m, ['win', 'd'])">显示桌面 (Win+D)</button>
                </div>
              </div>
            </div>
          </div>

          <!-- Section 2: Keyboard Macro Remap Card -->
          <div class="glass-panel remap-section-card mt-6">
            <div class="section-card-header">
              <div class="card-icon-title">
                <div class="section-icon-wrap key-wrap">
                  <Keyboard class="w-5 h-5 text-indigo-500" />
                </div>
                <div>
                  <h3 class="section-title">组合键映射</h3>
                  <p class="section-desc">将特定键盘组合键映射为目标按键输出</p>
                </div>
              </div>
              <button class="btn btn-secondary text-xs" @click="addKeyMapping">+ 添加映射</button>
            </div>

            <div class="overflow-hidden rounded-xl border border-color">
              <table class="data-table">
                <thead>
                  <tr>
                    <th style="width: 80px;">状态</th>
                    <th>触发键</th>
                    <th style="width: 40px; text-align: center;"></th>
                    <th>输出键</th>
                    <th>描述</th>
                    <th style="width: 90px; text-align: center;">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(km, idx) in config.mouse.mappings" :key="idx">
                    <td>
                      <label class="toggle-switch mini">
                        <input type="checkbox" v-model="km.enabled" @change="saveAll" />
                        <span class="slider"></span>
                      </label>
                    </td>
                    <td>
                      <div class="flex gap-1.5 items-center">
                        <span v-for="k in km.trigger" :key="k" class="keycap">{{ k.toUpperCase() }}</span>
                      </div>
                    </td>
                    <td style="text-align: center;">
                      <ArrowRight class="w-4 h-4 text-slate-400 inline-block" />
                    </td>
                    <td>
                      <div class="flex gap-1.5 items-center">
                        <span v-for="k in km.output" :key="k" class="keycap accent">{{ k.toUpperCase() }}</span>
                      </div>
                    </td>
                    <td>
                      <span class="text-xs text-secondary font-medium">{{ km.description }}</span>
                    </td>
                    <td style="text-align: center;">
                      <button class="btn-icon danger mx-auto" title="删除映射" @click="deleteKeyMapping(idx)">
                        <Trash2 class="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                  <tr v-if="config.mouse.mappings.length === 0">
                    <td colspan="6" class="text-center py-8 text-muted text-xs">
                      暂无组合键映射，点击右上角添加
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
                <span class="preset-label">快速选择：</span>
                <div class="preset-chips">
                  <button type="button" class="preset-chip active" @click="applyWebDavPreset('custom_server')">
                    <span class="preset-star">★</span> 自建服务 (175.178.147.236)
                  </button>
                  <button type="button" class="preset-chip" @click="applyWebDavPreset('jianguoyun')">坚果云</button>
                  <button type="button" class="preset-chip" @click="applyWebDavPreset('alist')">Alist</button>
                  <button type="button" class="preset-chip" @click="applyWebDavPreset('nextcloud')">Nextcloud</button>
                </div>
              </div>

              <div class="form-grid">
                <div class="form-item col-span-2">
                  <label class="form-label">服务器地址</label>
                  <input 
                    type="text" 
                    class="input-field" 
                    placeholder="http://175.178.147.236:7779/"
                    v-model="config.webdav.server_url" 
                  />
                  <span class="field-hint">支持 http / https 协议</span>
                </div>

                <div class="form-item">
                  <label class="form-label">用户名</label>
                  <input 
                    type="text" 
                    class="input-field" 
                    placeholder="gxy"
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
                  <label class="form-label">远程路径</label>
                  <input 
                    type="text" 
                    class="input-field font-mono" 
                    placeholder="bindx/bindx_config.json"
                    v-model="config.webdav.remote_filename" 
                  />
                  <span class="field-hint">建议填入 <code>bindx/bindx_config.json</code>，自动创建独立文件夹</span>
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
                  <span class="sync-label">远程目录:</span>
                  <span class="font-mono text-xs text-main">/bindx/</span>
                </div>
                <div class="sync-status-row">
                  <span class="sync-label">完整路径:</span>
                  <span class="font-mono text-xs text-muted truncate" :title="resolvedWebDavUrl">
                    {{ resolvedWebDavUrl || '未配置' }}
                  </span>
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
                    <p class="hero-ver">当前版本: <span class="font-mono font-semibold text-indigo-600">v2.0.0</span></p>
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
                  <span class="tile-desc">规则与设置持久化存储于本地 JSON 文件</span>
                </div>
                <div class="tile-action-path">
                  <span class="path-badge">data/bindx_config.json</span>
                  <button class="btn btn-secondary text-xs" title="在资源管理器中打开" @click="openDataFolder">
                    <FolderOpen class="w-3.5 h-3.5" />
                    <span>打开所在目录</span>
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
          <button class="modal-close" @click="hotkeyModal.show = false">×</button>
        </div>

        <div class="modal-body form-grid">
          <div class="form-item col-span-2">
            <label class="form-label">快捷键</label>
            <input 
              type="text" 
              class="input-field" 
              placeholder="例如: Ctrl+Alt+Q"
              v-model="hotkeyModal.data.hotkey"
            />
          </div>

          <div class="form-item">
            <label class="form-label">应用标识</label>
            <input 
              type="text" 
              class="input-field" 
              placeholder="例如: cloudmusic"
              v-model="hotkeyModal.data.app"
            />
          </div>

          <div class="form-item">
            <label class="form-label">目标类型</label>
            <select class="input-field" v-model="hotkeyModal.data.target_type">
              <option value="win32">桌面客户端</option>
              <option value="browser_tab">网页标签页</option>
              <option value="builtin">内置应用</option>
            </select>
          </div>

          <div v-if="hotkeyModal.data.target_type === 'browser_tab'" class="form-item col-span-2">
            <label class="form-label">标签页标题关键字</label>
            <input 
              type="text" 
              class="input-field" 
              placeholder="例如: 千问、Gemini"
              v-model="hotkeyModal.data.title_keyword"
            />
          </div>

          <div class="form-item col-span-2">
            <label class="form-label">程序文件名</label>
            <input 
              type="text" 
              class="input-field" 
              placeholder="例如: cloudmusic.exe，留空自动推断"
              v-model="hotkeyModal.data.exe_name"
            />
          </div>

          <div class="form-item col-span-2">
            <label class="form-label">程序路径</label>
            <input 
              type="text" 
              class="input-field" 
              placeholder="例如: C:\Program Files\App\app.exe"
              v-model="hotkeyModal.data.install_path"
            />
          </div>
        </div>

        <div class="modal-footer">
          <button class="btn btn-secondary" @click="hotkeyModal.show = false">取消</button>
          <button class="btn btn-primary" @click="saveHotkeyModal">保存</button>
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
  FolderOpen
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
      if (!data.app.theme) data.app.theme = 'light'
      config.value = data
    }
  } catch (e) {
    showToast('加载配置失败: ' + e, 'danger')
  }
}

// Save all changes
const saveAll = async () => {
  try {
    await invoke('update_config', { newConfig: config.value })
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

const openAddHotkeyModal = () => {
  hotkeyModal.value = {
    show: true,
    isEdit: false,
    index: -1,
    data: {
      app: '',
      hotkey: 'CTRL+ALT+W',
      enabled: true,
      launch_if_not_running: false,
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
}

const editHotkey = (entry, index) => {
  hotkeyModal.value = {
    show: true,
    isEdit: true,
    index,
    data: JSON.parse(JSON.stringify(entry))
  }
}

const saveHotkeyModal = () => {
  if (!hotkeyModal.value.data.hotkey.trim()) {
    showToast('快捷键组合不能为空', 'danger')
    return
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

// Mouse mappings
const updateMouseOutput = (mapping, text) => {
  const parts = text.split(/[\s,]+/).filter(Boolean)
  mapping.output = parts
  saveAll()
}

const addKeyMapping = () => {
  config.value.mouse.mappings.push({
    trigger: ['ctrl', 'p'],
    output: ['ctrl', 'alt', 'w'],
    description: '组合键映射',
    enabled: true
  })
  saveAll()
}

const deleteKeyMapping = (index) => {
  config.value.mouse.mappings.splice(index, 1)
  saveAll()
}

const setMousePreset = (mapping, keys) => {
  mapping.output = [...keys]
  saveAll()
  showToast(`已设为 ${keys.join('+').toUpperCase()}`, 'info')
}

// WebDAV Operations
const testingWebDav = ref(false)
const uploadingWebDav = ref(false)
const downloadingWebDav = ref(false)

const onTestWebDav = async () => {
  testingWebDav.value = true
  try {
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
    const downloaded = await invoke('download_from_webdav', { config: config.value.webdav })
    config.value = downloaded
    showToast('配置同步成功', 'success')
  } catch (e) {
    showToast('同步失败: ' + e, 'danger', 5000)
  } finally {
    downloadingWebDav.value = false
  }
}

const applyWebDavPreset = (preset) => {
  if (preset === 'custom_server') {
    config.value.webdav.server_url = 'http://175.178.147.236:7779/'
    config.value.webdav.username = 'gxy'
    config.value.webdav.password = '***REMOVED***'
    config.value.webdav.remote_filename = 'bindx/bindx_config.json'
    showToast('已载入自建服务配置', 'info')
  } else if (preset === 'jianguoyun') {
    config.value.webdav.server_url = 'https://dav.jianguoyun.com/dav/'
    config.value.webdav.remote_filename = 'bindx/bindx_config.json'
    showToast('已载入坚果云地址', 'info')
  } else if (preset === 'alist') {
    config.value.webdav.server_url = 'http://127.0.0.1:5244/dav/'
    config.value.webdav.remote_filename = 'bindx/bindx_config.json'
    showToast('已载入 Alist 地址', 'info')
  } else if (preset === 'nextcloud') {
    config.value.webdav.server_url = 'https://your-nextcloud.com/remote.php/dav/files/USERNAME/'
    config.value.webdav.remote_filename = 'bindx/bindx_config.json'
    showToast('已载入 Nextcloud 模板', 'info')
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

const openDataFolder = async () => {
  try {
    await invoke('open_external_url', { url: 'data' })
  } catch (e) {
    showToast('打开数据目录失败: ' + e, 'danger')
  }
}

const resolvedWebDavUrl = computed(() => {
  if (!config.value.webdav.server_url) return ''
  let base = config.value.webdav.server_url.trim()
  if (!base.endsWith('/')) base += '/'
  let path = (config.value.webdav.remote_filename || 'bindx/bindx_config.json').trim()
  while (path.startsWith('/')) path = path.slice(1)
  return base + path
})

// Global hook for tray
window.navigateToTab = (tab) => {
  currentTab.value = tab
}

onMounted(() => {
  fetchConfig()
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
  width: 215px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  padding: 16px 10px;
  flex-shrink: 0;
  gap: 4px;
  transition: background 0.25s ease, border-color 0.25s ease;
}

.nav-tab {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 11px 16px;
  border-radius: 10px;
  font-size: 13.5px;
  font-weight: 500;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all 0.16s ease;
  position: relative;
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

.mouse-cards-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}
.mouse-tile-card {
  padding: 20px;
  background: var(--bg-card-subtle);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  transition: all 0.2s ease;
}
.mouse-tile-card:hover {
  background: var(--bg-card);
  border-color: var(--border-hover);
  box-shadow: var(--card-shadow);
  transform: translateY(-1px);
}
.mouse-tile-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.mouse-badge-group {
  display: flex;
  align-items: center;
  gap: 12px;
}
.mouse-keycap {
  font-size: 13px;
  font-weight: 700;
  padding: 5px 12px;
  background: rgba(236, 72, 153, 0.12);
  color: #db2777;
  border-color: rgba(236, 72, 153, 0.3);
}
[data-theme="slate"] .mouse-keycap {
  background: rgba(236, 72, 153, 0.22);
  color: #f472b6;
  border-color: rgba(236, 72, 153, 0.45);
}
.mouse-btn-name {
  display: block;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-main);
}
.mouse-btn-desc {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 1px;
}
.mouse-mapping-flow {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: var(--bg-card);
  border-radius: 8px;
  border: 1px solid var(--border-color);
}
.flow-step {
  display: flex;
  align-items: center;
  gap: 8px;
}
.flow-label {
  font-size: 11.5px;
  color: var(--text-muted);
  font-weight: 500;
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
.mouse-input-row {
  width: 100%;
}
.quick-presets {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.preset-hint {
  font-size: 11.5px;
  color: var(--text-dim);
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
  grid-template-columns: 1.35fr 1fr;
  gap: 20px;
  align-items: start;
}
.webdav-card {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  border-radius: 14px;
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
}
.sync-status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12.5px;
  gap: 10px;
}
.sync-label {
  color: var(--text-secondary);
  font-weight: 500;
  flex-shrink: 0;
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
  grid-template-columns: 1.15fr 1fr;
  gap: 20px;
  align-items: start;
}
.version-hero-card {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  border-radius: 14px;
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
  font-size: 12px;
  padding: 6px 12px;
  border-radius: 8px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
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
}
.modal-dialog {
  width: 520px;
  padding: 28px;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
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
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
  padding-top: 18px;
  border-top: 1px solid var(--border-color);
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
