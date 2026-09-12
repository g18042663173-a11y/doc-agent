import { Alert } from 'antd';

export default function ErrorMessage({ message }: { message: string }) {
  return <Alert type="error" showIcon title={message} />;
}
