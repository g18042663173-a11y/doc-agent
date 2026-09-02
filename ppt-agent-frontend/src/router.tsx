import { Navigate, createBrowserRouter } from 'react-router-dom';
import MainLayout from '@/components/Layout/MainLayout';
import Dashboard from '@/pages/Dashboard';
import SmartGenerate from '@/pages/Generate/Smart';
import OutlineGenerate from '@/pages/Generate/Outline';
import AICodingBridge from '@/pages/Generate/AICodingBridge';
import Templates from '@/pages/Design/Templates';
import Colors from '@/pages/Design/Colors';
import Charts from '@/pages/Design/Charts';
import SmartArt from '@/pages/Design/SmartArt';
import NGA from '@/pages/Config/NGA';
import Settings from '@/pages/Config/Settings';
import DataImport from '@/pages/Data/Import';
import DataManage from '@/pages/Data/Manage';
import Preview from '@/pages/Preview';
import Export from '@/pages/Export';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: 'dashboard', element: <Dashboard /> },
      { path: 'generate/smart', element: <SmartGenerate /> },
      { path: 'generate/outline', element: <OutlineGenerate /> },
      { path: 'generate/aicoding', element: <AICodingBridge /> },
      { path: 'design/templates', element: <Templates /> },
      { path: 'design/colors', element: <Colors /> },
      { path: 'design/charts', element: <Charts /> },
      { path: 'design/smartart', element: <SmartArt /> },
      { path: 'config/nga', element: <NGA /> },
      { path: 'config/settings', element: <Settings /> },
      { path: 'data/import', element: <DataImport /> },
      { path: 'data/manage', element: <DataManage /> },
      { path: 'preview', element: <Preview /> },
      { path: 'export', element: <Export /> },
      { path: 'users', element: <Navigate to="/config/nga" replace /> }
    ]
  }
]);
