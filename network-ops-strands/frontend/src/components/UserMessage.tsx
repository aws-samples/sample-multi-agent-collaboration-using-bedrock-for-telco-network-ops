import React from 'react';
import { User } from 'lucide-react';
import type { IMessage } from '../types';

interface IUserMessageProps {
  message: IMessage;
}

export const UserMessage: React.FC<IUserMessageProps> = ({ message }) => {
  return (
    <div className="flex gap-3 justify-end animate-fadeIn">
      <div className="max-w-3xl rounded-2xl px-5 py-3 bg-gradient-to-br from-indigo-600 to-indigo-700 text-white shadow-md">
        <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">
          {message.content}
        </p>
      </div>
      <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gradient-to-br from-indigo-600 to-indigo-700 flex items-center justify-center text-white shadow-md">
        <User className="w-5 h-5" />
      </div>
    </div>
  );
};
