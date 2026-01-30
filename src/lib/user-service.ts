import { supabase } from './supabase';

export async function saveUserProgress(userId: string, index: number) {
    try {
        const { error } = await supabase
            .from('pmp_user_progress')
            .upsert({
                user_id: userId,
                last_question_index: index,
                updated_at: new Date().toISOString(),
            }, { onConflict: 'user_id' });

        if (error) throw error;
    } catch (error) {
        console.error('Error saving user progress:', error);
    }
}

export async function getUserProgress(userId: string): Promise<number | null> {
    try {
        const { data, error } = await supabase
            .from('pmp_user_progress')
            .select('last_question_index')
            .eq('user_id', userId)
            .single();

        if (error) {
            if (error.code === 'PGRST116') {
                return null;
            }
            console.error('Supabase error fetching progress:', error);
            throw error;
        }

        return data?.last_question_index ?? null;
    } catch (error) {
        console.error('Error getting user progress:', error);
        return null;
    }
}

export async function checkUserApprovalStatus(userId: string): Promise<boolean> {
    try {
        const { data, error } = await supabase
            .from('profiles')
            .select('is_approved')
            .eq('id', userId)
            .single();

        if (error) {
            console.warn('Profile not found, defaulting to false approval', error);
            return false;
        }

        return data?.is_approved ?? false;
    } catch (error) {
        console.error('Error checking approval status:', error);
        return false;
    }
}
