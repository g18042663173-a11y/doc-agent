import { Row, Col } from 'antd';
import { useState } from 'react';
import NGAConfigForm from '@/components/ConfigManager/NGAConfigForm';
import UserList from '@/components/ConfigManager/UserList';

export default function NGA() {
  const [refreshToken, setRefreshToken] = useState(0);

  return (
    <Row gutter={16}>
      <Col xs={24} lg={9}><NGAConfigForm onSaved={() => setRefreshToken((value) => value + 1)} /></Col>
      <Col xs={24} lg={15}><UserList refreshToken={refreshToken} /></Col>
    </Row>
  );
}
