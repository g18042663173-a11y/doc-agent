import { Alert } from 'antd';

export default function SuccessMessage({ message }: { message: string }) {
  return <Alert type="success" showIcon title={message} />;
}
