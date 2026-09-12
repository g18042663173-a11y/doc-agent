import {
  AppstoreOutlined,
  BgColorsOutlined,
  DashboardOutlined,
  FilePptOutlined,
  NodeIndexOutlined,
  PartitionOutlined,
  SettingOutlined,
  ToolOutlined,
  UploadOutlined
} from '@ant-design/icons';
import { Grid, Layout, Menu } from 'antd';
import type { MenuProps } from 'antd';
import { useLocation, useNavigate } from 'react-router-dom';
import { useUIStore } from '@/store';

const { Sider } = Layout;
const { useBreakpoint } = Grid;

const items: MenuProps['items'] = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表板' },
  {
    key: 'generate',
    icon: <FilePptOutlined />,
    label: '生成',
    children: [
      { key: '/generate/smart', label: '智能生成' },
      { key: '/generate/outline', label: '大纲生成' }
    ]
  },
  {
    key: 'design',
    icon: <AppstoreOutlined />,
    label: '设计',
    children: [
      { key: '/design/templates', icon: <FilePptOutlined />, label: '模板' },
      { key: '/design/colors', icon: <BgColorsOutlined />, label: '颜色' }
    ]
  },
  {
    key: 'config',
    icon: <SettingOutlined />,
    label: '配置',
    children: [
      { key: '/config/nga', label: '模型档案' },
      { key: '/config/settings', label: '设置' }
    ]
  },
  {
    key: 'tools',
    icon: <ToolOutlined />,
    label: '辅助工具',
    children: [
      { key: '/generate/aicoding', label: 'AICoding 桥接' },
      { key: '/design/charts', icon: <NodeIndexOutlined />, label: '图表实验' },
      { key: '/design/smartart', icon: <PartitionOutlined />, label: 'SmartArt 实验' },
      { key: '/data/import', label: '数据导入' },
      { key: '/data/manage', label: '数据管理' },
      { key: '/preview', icon: <FilePptOutlined />, label: '预览' },
      { key: '/export', icon: <UploadOutlined />, label: '导出' }
    ]
  }
];

export default function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const collapsed = useUIStore((state) => state.collapsed);
  const screens = useBreakpoint();

  if (!screens.md) {
    return (
      <nav className="mobile-nav" aria-label="主导航">
        <div className="mobile-brand">
          <span className="brand-logo">P</span>
          <span className="brand-name">PPT Agent</span>
        </div>
        <Menu
          mode="horizontal"
          selectedKeys={[location.pathname]}
          items={items}
          onClick={({ key }) => navigate(key)}
        />
      </nav>
    );
  }

  return (
    <Sider width={248} collapsed={collapsed} className="app-sidebar">
      <div className="brand-mark">
        <span className="brand-logo">P</span>
        {!collapsed && <span className="brand-name">PPT Agent</span>}
      </div>
      <Menu
        mode="inline"
        selectedKeys={[location.pathname]}
        defaultOpenKeys={['generate', 'design', 'config', 'tools']}
        items={items}
        onClick={({ key }) => navigate(key)}
      />
    </Sider>
  );
}
