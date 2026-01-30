import React from 'react';
import { LanguageSelector } from './LanguageSelector';
import { AuthButton } from './AuthButton';
import type { Language } from '../types';
import '../styles/Header.css';

interface HeaderProps {
    currentLanguage: Language;
    onLanguageChange: (language: Language) => void;
    onHistoryClick?: () => void;
    isHistoryView?: boolean;
    user?: any;
    isAdmin?: boolean;
    onAdminClick?: () => void;
    isAdminView?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
    currentLanguage,
    onLanguageChange,
    onHistoryClick,
    isHistoryView,
    user,
    isAdmin,
    onAdminClick,
    isAdminView
}) => {
    return (
        <header className="app-header">
            <div className="container">
                <div className="header-content">
                    <AuthButton currentLanguage={currentLanguage} />

                    {user && onHistoryClick && (
                        <div className="history-actions" style={{ display: 'flex', gap: '10px' }}>
                            {isAdmin && (
                                <button
                                    className={`btn-history ${isAdminView ? 'active' : ''}`}
                                    onClick={onAdminClick}
                                >
                                    {isAdminView ? 'Back to Quiz' : 'Admin'}
                                </button>
                            )}

                            {!isAdminView && (
                                <button
                                    className={`btn-history ${isHistoryView ? 'active' : ''}`}
                                    onClick={onHistoryClick}
                                >
                                    {isHistoryView ? (
                                        <>
                                            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                <line x1="19" y1="12" x2="5" y2="12"></line>
                                                <polyline points="12 19 5 12 12 5"></polyline>
                                            </svg>
                                            Back to Quiz
                                        </>
                                    ) : (
                                        <>
                                            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                <circle cx="12" cy="12" r="10"></circle>
                                                <polyline points="12 6 12 12 16 14"></polyline>
                                            </svg>
                                            My History
                                        </>
                                    )}
                                </button>
                            )}
                        </div>
                    )}

                    <LanguageSelector
                        currentLanguage={currentLanguage}
                        onLanguageChange={onLanguageChange}
                    />
                    <h1 className="app-title">
                        PMP Exam Master
                    </h1>
                    <p className="app-subtitle">
                        Pass the PMI Project Management Professional Exam
                    </p>
                </div>
            </div>
        </header>
    );
};
