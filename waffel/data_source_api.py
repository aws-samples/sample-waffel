#!/usr/bin/env python3

import boto3
from collections import defaultdict
from InquirerPy import inquirer
from .data_source import DataSource
from .config import WAFFELConfig

class APIDataSource(DataSource):
    """API-based data source using Well-Architected API"""
    
    def __init__(self, workload_id=None, lens_alias=None):
        self.workload_id = workload_id
        self.lens_alias = lens_alias
        self.wa_client = boto3.client('wellarchitected')
        self.config = WAFFELConfig()
    
    def get_workloads(self):
        workloads = []
        response = self.wa_client.list_workloads(MaxResults=50)
        workloads.extend(response['WorkloadSummaries'])
        
        while 'NextToken' in response:
            response = self.wa_client.list_workloads(MaxResults=50, NextToken=response['NextToken'])
            workloads.extend(response['WorkloadSummaries'])
        
        return workloads
    
    def get_lenses(self, workload_id):
        return self.wa_client.list_lens_reviews(WorkloadId=workload_id)['LensReviewSummaries']
    
    def get_answers(self, workload_id, lens_alias):
        params = {'WorkloadId': workload_id, 'LensAlias': lens_alias, 'MaxResults': 50}
        
        answers = []
        response = self.wa_client.list_answers(**params)
        answers.extend(response['AnswerSummaries'])
        
        while 'NextToken' in response:
            params['NextToken'] = response['NextToken']
            response = self.wa_client.list_answers(**params)
            answers.extend(response['AnswerSummaries'])
        
        return answers
    
    def get_answer_detail(self, workload_id, lens_alias, question_id):
        params = {'WorkloadId': workload_id, 'LensAlias': lens_alias, 'QuestionId': question_id}
        return self.wa_client.get_answer(**params)['Answer']
    
    def select_workload_interactive(self):
        """Interactive workload selection"""
        workloads = self.get_workloads()
        
        choices = []
        for w in workloads:
            description = w.get('Description', 'No description')
            if len(description) > 60:
                description = description[:57] + "..."
            choices.append(f"{w['WorkloadName']} - {description}")
        
        if not choices:
            raise ValueError("No workloads found")
        
        workload_choice = inquirer.select(
            message="Select a workload:",
            choices=choices
        ).execute()
        
        workload_name = workload_choice.split(' - ')[0]
        return next(w['WorkloadId'] for w in workloads if w['WorkloadName'] == workload_name)
    
    def select_lens_interactive(self, workload_id):
        """Interactive lens selection"""
        lenses = self.get_lenses(workload_id)
        
        if not lenses:
            raise ValueError("No lenses found for this workload")
        
        lens_choices = [l['LensName'] for l in lenses]
        
        lens_choice = inquirer.select(
            message="Select a lens:",
            choices=lens_choices
        ).execute()
        
        return next(l['LensAlias'] for l in lenses if l['LensName'] == lens_choice)
    
    def convert_api_to_standard_format(self, workload_id, lens_alias):
        """Convert API data to standardized format matching PDF structure"""
        
        # Get workload details
        workload = self.wa_client.get_workload(WorkloadId=workload_id)['Workload']
        
        # Get answers
        answers = self.get_answers(workload_id, lens_alias)
        
        # Organize by pillars
        pillars = defaultdict(list)
        for answer in answers:
            pillar = answer['PillarId']
            
            # Get detailed answer
            detail = self.get_answer_detail(workload_id, lens_alias, answer['QuestionId'])
            
            # Count choice statistics
            selected_choices = detail.get('SelectedChoices', [])
            selected_count = len(selected_choices)
            total_choices = len(detail.get('Choices', []))
            not_selected_count = total_choices - selected_count
            
            # Map API risk levels to Excel format
            risk_mapping = {
                'HIGH': 'High Risk',
                'MEDIUM': 'Medium Risk', 
                'LOW': 'Low Risk',
                'UNANSWERED': 'Not Assessed',
                'NOT_APPLICABLE': 'Not Applicable'
            }
            risk_level = risk_mapping.get(answer.get('Risk', 'UNANSWERED'), 'Not Assessed')
            
            # Convert to PDF-like format
            question_data = {
                'question_id': answer['QuestionId'],
                'question': detail['QuestionTitle'],
                'question_title': detail['QuestionTitle'],
                'question_description': detail.get('QuestionDescription', ''),
                'pillar': pillar,
                'risk_level': risk_level,
                'notes': detail.get('Notes', ''),
                'improvement_plan': '',  # Will be populated from unselected choices
                'choices': [],
                'stats': {
                    'selected': selected_count,
                    'not_selected': not_selected_count,
                    'na': 0  # API doesn't have N/A choices
                },
                'improvement_items': []
            }
            
            # Add choices
            improvement_items = []
            improvement_plan_text = []
            
            for choice in detail.get('Choices', []):
                is_selected = choice['ChoiceId'] in selected_choices
                status = '✅ Selected' if is_selected else '⚠️ Not Selected'
                
                question_data['choices'].append({
                    'choice_id': choice['ChoiceId'],
                    'choice': choice['Title'],  # Use 'choice' key to match PDF format
                    'title': choice['Title'],
                    'description': choice.get('Description', ''),
                    'status': status
                })
                
                # Add unselected choices as improvement items (excluding "None of these")
                if not is_selected and choice['ChoiceId'] != f"{answer['QuestionId']}_no" and "None of these" not in choice['Title']:
                    improvement_url = detail.get('ImprovementPlanUrl', '')
                    improvement_items.append({
                        'item': choice['Title'],
                        'url': improvement_url
                    })
                    improvement_plan_text.append(choice['Title'])
            
            # Set improvement plan text and items
            question_data['improvement_plan'] = '\n'.join(improvement_plan_text)
            question_data['improvement_items'] = improvement_items
            
            pillars[pillar].append(question_data)
        
        workload_properties = {
            'Workload name': workload['WorkloadName'],
            'ARN': workload['WorkloadArn'],
            'Description': workload.get('Description', ''),
            'Review owner': workload.get('Owner', ''),
            'Environment': workload.get('Environment', ''),
            'AWS Regions': ', '.join(workload.get('AwsRegions', [])),
            'Account IDs': ', '.join(workload.get('AccountIds', []))
        }
        
        return {
            'workload_properties': workload_properties,
            'pillars': dict(pillars),
            'source_type': 'api',
            'source_info': f"Workload: {workload_id}"
        }
    
    def get_workload_data(self):
        """Get workload data, prompting for missing parameters"""
        
        # Get workload ID if not provided
        if not self.workload_id:
            self.workload_id = self.select_workload_interactive()
        
        # Get lens alias if not provided
        if not self.lens_alias:
            self.lens_alias = self.select_lens_interactive(self.workload_id)
        
        return self.convert_api_to_standard_format(self.workload_id, self.lens_alias)
